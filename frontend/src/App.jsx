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
  
    const stopsFound = {};
    const vehicleMarkers = [];
    const visited = new Set();
  
    const agencyEndpoints = {
      muni: {
        nearby: `${BASE_URL}/bus/nearby-stops`,
        vehicles: `${BASE_URL}/bus-positions/by-stop`,
        codes: ['SF', 'SFMTA', 'muni']
      },
      bart: {
        nearby: `${BASE_URL}/bart-positions/nearby-stops`,
        vehicles: `${BASE_URL}/bart-positions/by-stop`,
        codes: ['BA', 'bart']
      }
    };
  
    const fetchByAgency = async (group) => {
      try {
        const res = await fetch(`${group.nearby}?lat=${location.lat}&lon=${location.lng}&radius=${radius}`);
        if (!res.ok) throw new Error("Failed to fetch nearby stops.");
        const stops = await res.json();
  
        for (const stop of stops) {
          const stopCode = stop.stop_code || stop.stop_id;
          const key = `${stopCode}-${group.codes[0]}`;
          if (visited.has(key)) continue;
  
          visited.add(key);
          stopsFound[stop.stop_id] = stop;
  
          const res = await fetch(`${group.vehicles}?stopCode=${stopCode}&agency=${group.codes[0]}`);
          if (!res.ok) continue;
  
          const data = await res.json();
          const visits = data?.ServiceDelivery?.StopMonitoringDelivery?.MonitoredStopVisit ?? [];
  
          visits.forEach((visit, i) => {
            const vehicle = visit.MonitoredVehicleJourney;
            const loc = vehicle?.VehicleLocation;
            if (!loc?.Latitude || !loc?.Longitude) return;
  
            vehicleMarkers.push({
              position: { lat: parseFloat(loc.Latitude), lng: parseFloat(loc.Longitude) },
              title: `${vehicle?.PublishedLineName || "Transit"} → ${vehicle?.MonitoredCall?.DestinationDisplay || "?"}`,
              stopId: `${stopCode}-${group.codes[0]}-${i}`,
              icon: {
                url: '/images/live-bus-icon.svg',
                scaledSize: { width: 28, height: 28 }
              }
            });
          });
        }
      } catch (err) {
        console.warn(`[FETCH ERROR] ${group.codes[0]}: ${err.message}`);
      }
    };
  
    await Promise.all([
      fetchByAgency(agencyEndpoints.muni),
      fetchByAgency(agencyEndpoints.bart)
    ]);
  
    const stopMarkers = Object.values(stopsFound).map((stop) => ({
      position: { lat: parseFloat(stop.stop_lat), lng: parseFloat(stop.stop_lon) },
      title: stop.stop_name,
      stopId: stop.stop_id,
      icon: { url: '/images/bus-stop-icon.svg', scaledSize: { width: 32, height: 32 } }
    }));
  
    if (userLocation) {
      stopMarkers.push({
        position: userLocation,
        title: 'You',
        icon: { url: '/images/user-location-icon.svg', scaledSize: { width: 32, height: 32 } }
      });
    }
  
    setNearbyStops(stopsFound);
    setMarkers([...stopMarkers, ...vehicleMarkers]);
    setLiveVehicleMarkers(vehicleMarkers);
    setIsLoading(false);
  };
  
  useEffect(() => {
    const fetchLiveMarkers = async () => {
      let allMarkers = [];
  
      for (const stop of Object.values(nearbyStops)) {
        const stopCode = stop.stop_code || stop.stop_id;
        const agency = (stop.agency || "muni").toLowerCase();
  
        try {
          const res = await fetch(`${BASE_URL}/bus-positions/by-stop?stopCode=${stopCode}&agency=${agency}`);
          const json = await res.json();
  
          const visits = json?.ServiceDelivery?.StopMonitoringDelivery?.MonitoredStopVisit ?? [];
  
          const markers = visits.map((visit, index) => {
            const loc = visit?.MonitoredVehicleJourney?.VehicleLocation;
            if (!loc?.Latitude || !loc?.Longitude) return null;
  
            return {
              position: {
                lat: parseFloat(loc.Latitude),
                lng: parseFloat(loc.Longitude)
              },
              title: `${visit.MonitoredVehicleJourney?.PublishedLineName || "Transit"} → ${visit.MonitoredVehicleJourney?.MonitoredCall?.DestinationDisplay || "?"}`,
              stopId: `${stopCode}-${agency}-${index}`,
              icon: {
                url: '/images/live-bus-icon.svg',
                scaledSize: { width: 28, height: 28 }
              }
            };
          }).filter(Boolean);
  
          allMarkers.push(...markers);
        } catch (err) {
          console.warn(`❌ Live fetch failed: ${stopCode} (${agency}): ${err.message}`);
        }
      }
  
      setLiveVehicleMarkers(allMarkers);
    };
  
    if (Object.keys(nearbyStops).length > 0) {
      fetchLiveMarkers();
    }
  }, [nearbyStops]);
  
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
              markers={markers}
              liveVehicleMarkers={liveVehicleMarkers}
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
