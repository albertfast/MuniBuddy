// Updated App.jsx with live vehicle markers and improved dark theme readability
import React, { useState, useEffect } from 'react';
import {
  Container, Box, Typography, Alert, TextField, InputAdornment,
  Slider, Grid, Button, Dialog, DialogTitle, DialogContent, DialogActions,
  CircularProgress
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import MyLocationIcon from '@mui/icons-material/MyLocation';
import Map from './components/Map';
import TransitInfo from './components/TransitInfo';
import { geocodeAddress, parseCoordinates, formatCoordinates } from './utility/geocode';
import './index.css';

const BASE_URL = import.meta.env.VITE_API_BASE;

const App = () => {
  const [userLocation, setUserLocation] = useState(null);
  const [nearbyStops, setNearbyStops] = useState({});
  const [error, setError] = useState(null);
  const [markers, setMarkers] = useState([]);
  const [liveVehicleMarkers, setLiveVehicleMarkers] = useState([]);
  const [searchAddress, setSearchAddress] = useState('');
  const [radius, setRadius] = useState(0.15);
  const [isLoading, setIsLoading] = useState(false);
  const [theme, setTheme] = useState('light');
  const [showLocationDialog, setShowLocationDialog] = useState(true);

  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute('data-theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

  const requestLocation = () => {
    setShowLocationDialog(false);
    if (navigator.geolocation) {
      setIsLoading(true);
      setError(null);
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const location = { lat: pos.coords.latitude, lng: pos.coords.longitude };
          setUserLocation(location);
          fetchNearbyStops(location);
        },
        () => {
          setError('Could not get location. Please allow location access or enter manually.');
          setIsLoading(false);
        }
      );
    } else {
      setError('Geolocation is not supported.');
      setIsLoading(false);
    }
  };

  const fetchNearbyStops = async (location) => {
    if (!location) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${BASE_URL}/nearby-stops?lat=${location.lat}&lon=${location.lng}&radius=${radius}`);
      if (!res.ok) throw new Error("Could not load stops");
      const data = await res.json();
      setNearbyStops(data);

      const stopMarkers = Object.entries(data).map(([id, stop]) => ({
        position: { lat: parseFloat(stop.stop_lat), lng: parseFloat(stop.stop_lon) },
        title: stop.stop_name,
        stopId: id,
        icon: { url: '/images/bus-stop-icon32.svg', scaledSize: { width: 32, height: 32 } }
      }));

      if (userLocation) {
        stopMarkers.push({
          position: userLocation,
          title: 'You',
          icon: { url: '/images/user-location-icon.svg', scaledSize: { width: 32, height: 32 } }
        });
      }

      setMarkers([...stopMarkers, ...liveVehicleMarkers]);
    } catch (err) {
      setError("Failed to load nearby stops.");
      setNearbyStops({});
    } finally {
      setIsLoading(false);
    }
  };

  const handleManualLocationSearch = async () => {
    const input = searchAddress.trim();
    if (!input) {
      setError("Please enter coordinates or an address.");
      return;
    }
    setIsLoading(true);
    setError(null);
    const coords = parseCoordinates(input);
    if (coords) {
      setUserLocation(coords);
      fetchNearbyStops(coords);
      setIsLoading(false);
      return;
    }
    try {
      const data = await geocodeAddress(input);
      if (data?.lat && data?.lng) {
        const location = { lat: data.lat, lng: data.lng };
        setUserLocation(location);
        setSearchAddress(formatCoordinates(data.lat, data.lng));
        fetchNearbyStops(location);
      } else {
        setError("Could not find coordinates. Try a more specific address.");
      }
    } catch (err) {
      setError(`Geocoding failed: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Container maxWidth="lg">
      <Box sx={{ my: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h4">MuniBuddy</Typography>
        <div>
          <button onClick={toggleTheme}>
            {theme === 'light' ? 'Switch to Dark Theme' : 'Switch to Light Theme'}
          </button>
          <p>Hello, this is a themed app!</p>
        </div>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Grid container spacing={2} alignItems="center" sx={{ mb: 2 }}>
        <Grid item xs={12} sm={8}>
          <TextField
            fullWidth
            placeholder="Enter address or coordinates"
            value={searchAddress}
            onChange={(e) => setSearchAddress(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleManualLocationSearch()}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
              style: { color: theme === 'dark' ? '#fff' : '#000' },
            }}
          />
        </Grid>
        <Grid item xs={6} sm={2}>
          <Button fullWidth variant="contained" onClick={handleManualLocationSearch}>Search</Button>
        </Grid>
        <Grid item xs={6} sm={2}>
          <Button fullWidth variant="outlined" onClick={requestLocation} startIcon={<MyLocationIcon />}>Locate Me</Button>
        </Grid>
        <Grid item xs={12}>
          <Typography gutterBottom>Radius: {radius.toFixed(2)} mi</Typography>
          <Slider value={radius} min={0.1} max={1.0} step={0.05} onChange={(e, v) => setRadius(v)} valueLabelDisplay="auto" />
        </Grid>
      </Grid>

      <Grid container spacing={2}>
        <Grid item xs={12} md={8}>
          <Box className="map-container" sx={{ position: 'relative', height: '450px', mb: { xs: 3, md: 0 } }}>
            <Map
              center={userLocation || { lat: 37.7749, lng: -122.4194 }}
              markers={[...markers, ...liveVehicleMarkers]}
              onMapClick={(e) => {
                const location = { lat: e.latLng.lat(), lng: e.latLng.lng() };
                setUserLocation(location);
                setSearchAddress(formatCoordinates(location.lat, location.lng));
                fetchNearbyStops(location);
              }}
            />
            {isLoading && (
              <Box sx={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(255,255,255,0.5)', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                <CircularProgress />
              </Box>
            )}
          </Box>
        </Grid>
        <Grid item xs={12} md={4} className="transit-info-panel">
          {!isLoading && Object.keys(nearbyStops).length > 0 ? (
            <TransitInfo stops={nearbyStops} setLiveVehicleMarkers={setLiveVehicleMarkers} />
          ) : (
            !isLoading && (
              <Typography align="center" color="text.secondary" sx={{ py: 3 }}>
                {userLocation ? 'No nearby stops found.' : 'Enter or select a location to see stops.'}
              </Typography>
            )
          )}
        </Grid>
      </Grid>

      <Dialog open={showLocationDialog} onClose={() => setShowLocationDialog(false)}>
        <DialogTitle>Use Your Location?</DialogTitle>
        <DialogContent>
          <Typography>Allow MuniBuddy to use your current location to find nearby transit stops?</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowLocationDialog(false)}>No Thanks</Button>
          <Button onClick={requestLocation} variant="contained">Use Location</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default App;
