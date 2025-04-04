import React, { useState } from 'react';
import {
  Container,
  Box,
  Paper,
  Typography,
  Alert,
  TextField,
  InputAdornment,
  Slider,
  Grid,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import MyLocationIcon from '@mui/icons-material/MyLocation';
import Map from './components/Map';
import TransitInfo from './components/TransitInfo';

// 🔍 DEBUG: Log environment variables
const BASE_URL = import.meta.env.VITE_API_BASE;
const GOOGLE_MAPS_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

console.log("✅ VITE_API_BASE:", BASE_URL);
console.log("✅ VITE_GOOGLE_MAPS_API_KEY:", GOOGLE_MAPS_KEY);

const App = () => {
  const [userLocation, setUserLocation] = useState(null);
  const [nearbyStops, setNearbyStops] = useState({});
  const [error, setError] = useState(null);
  const [markers, setMarkers] = useState([]);
  const [searchAddress, setSearchAddress] = useState('');
  const [radius, setRadius] = useState(0.15);
  const [showLocationDialog, setShowLocationDialog] = useState(true);

  const requestLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const location = {
            lat: position.coords.latitude,
            lng: position.coords.longitude
          };
          setUserLocation(location);
          fetchNearbyStops(location);
          setShowLocationDialog(false);
        },
        (err) => {
          console.error("Geolocation error:", err);
          setError('Please enable location services or enter coordinates manually.');
          setShowLocationDialog(false);
        }
      );
    } else {
      setError('Geolocation is not supported by your browser.');
      setShowLocationDialog(false);
    }
  };

  const fetchNearbyStops = async (location) => {
    try {
      setError(null);
      const url = `${BASE_URL}/nearby-stops?lat=${location.lat}&lon=${location.lng}&radius_miles=${radius}`;
      console.log("📡 Fetching:", url);
      const response = await fetch(url);
      const data = await response.json();

      if (data) {
        setNearbyStops(data);
        const newMarkers = Object.entries(data).map(([stopId, stop]) => ({
          position: {
            lat: parseFloat(stop.stop_lat),
            lng: parseFloat(stop.stop_lon)
          },
          title: stop.stop_name,
          stopId,
          icon: {
            url: '/images/bus-stop-icon.png',
            scaledSize: { width: 32, height: 32 }
          }
        }));

        if (userLocation) {
          newMarkers.push({
            position: userLocation,
            title: 'Your Location',
            icon: {
              url: '/images/user-location-icon.png',
              scaledSize: { width: 32, height: 32 }
            }
          });
        }

        setMarkers(newMarkers);
      }
    } catch (err) {
      console.error("❌ Nearby stop fetch error:", err);
      setError('Could not load nearby stops. Please try again later.');
    }
  };

  const handleMapClick = (event) => {
    const location = {
      lat: event.latLng.lat(),
      lng: event.latLng.lng()
    };
    console.log("🗺️ Clicked Location:", location);
    setUserLocation(location);
    fetchNearbyStops(location);
  };

  const handleRadiusChange = (event, newValue) => {
    setRadius(newValue);
    if (userLocation) {
      fetchNearbyStops(userLocation);
    }
  };

  const handleManualLocation = () => {
    const [lat, lon] = searchAddress.split(',').map((x) => parseFloat(x.trim()));
    if (!isNaN(lat) && !isNaN(lon)) {
      const location = { lat, lng: lon };
      setUserLocation(location);
      fetchNearbyStops(location);
    } else {
      setError('Please enter valid coordinates like: 37.7749, -122.4194');
    }
  };

  return (
    <Container maxWidth="lg">
      <Box sx={{ my: 4 }}>
        <Typography variant="h4" gutterBottom>
          MuniBuddy - SF Transit Finder
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Grid container spacing={2} sx={{ mb: 2 }}>
          <Grid item xs={12} md={6}>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <TextField
                fullWidth
                placeholder="Enter coordinates (lat, lon)"
                value={searchAddress}
                onChange={(e) => setSearchAddress(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleManualLocation()}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon />
                    </InputAdornment>
                  )
                }}
              />
              <IconButton color="primary" onClick={requestLocation}>
                <MyLocationIcon />
              </IconButton>
              <Button variant="contained" onClick={handleManualLocation}>
                Search
              </Button>
            </Box>
          </Grid>

          <Grid item xs={12} md={6}>
            <Box sx={{ px: 2 }}>
              <Typography>Search Radius: {radius} miles</Typography>
              <Slider
                value={radius}
                onChange={handleRadiusChange}
                min={0.1}
                max={1.0}
                step={0.05}
                marks={[
                  { value: 0.1, label: '0.1' },
                  { value: 0.5, label: '0.5' },
                  { value: 1.0, label: '1.0' }
                ]}
                valueLabelDisplay="auto"
              />
            </Box>
          </Grid>
        </Grid>

        <Paper elevation={3} sx={{ height: '400px', position: 'relative', mb: 4 }}>
          <Map
            center={userLocation || { lat: 37.7749, lng: -122.4194 }}
            markers={markers}
            onMapClick={handleMapClick}
            zoom={15}
          />
        </Paper>

        {Object.keys(nearbyStops).length > 0 ? (
          <TransitInfo stops={nearbyStops} />
        ) : (
          <Typography align="center" color="textSecondary">
            No stops found nearby. Try a different location or increase the radius.
          </Typography>
        )}
      </Box>

      <Dialog open={showLocationDialog} onClose={() => setShowLocationDialog(false)}>
        <DialogTitle>Use Your Location?</DialogTitle>
        <DialogContent>
          <Typography>
            Allow MuniBuddy to use your current location to find nearby transit stops?
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowLocationDialog(false)}>No</Button>
          <Button onClick={requestLocation} variant="contained">Yes</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default App;
