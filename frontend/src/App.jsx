import React, { useState, useEffect } from 'react';
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
  IconButton,
  AlertTitle,
  CircularProgress
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import MyLocationIcon from '@mui/icons-material/MyLocation';
import axios from 'axios';
import Map from './components/Map';
import TransitInfo from './components/TransitInfo';

const App = () => {
  const [userLocation, setUserLocation] = useState(null);
  const [nearbyStops, setNearbyStops] = useState({});
  const [error, setError] = useState(null);
  const [markers, setMarkers] = useState([]);
  const [searchAddress, setSearchAddress] = useState('');
  const [radius, setRadius] = useState(0.15);
  const [showLocationDialog, setShowLocationDialog] = useState(true);
  const [locationStatus, setLocationStatus] = useState('');
  const [locatingInProgress, setLocatingInProgress] = useState(false);
  const [fetchingStops, setFetchingStops] = useState(false);
  const [fetchTimeout, setFetchTimeout] = useState(null);

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
        (error) => {
          console.error('Error getting location:', error);
          setError('Please enable location services or enter an address manually.');
          setShowLocationDialog(false);
        }
      );
    } else {
      setError('Geolocation is not supported by your browser. Please enter an address manually.');
      setShowLocationDialog(false);
    }
  };

  const fetchNearbyStops = async (location) => {
    try {
      setError(null);
      setFetchingStops(true);
      
      // Set a timeout to show a message if the fetch takes too long
      const timeoutId = setTimeout(() => {
        console.log('Fetch is taking longer than expected...');
        setError('Fetching stops is taking longer than expected. Please wait...');
      }, 5000); // Show message after 5 seconds
      
      setFetchTimeout(timeoutId);
      
      console.log('Fetching stops at:', location);
      const response = await axios.get(`${import.meta.env.VITE_API_BASE}/nearby-stops`, {
        params: {
          lat: location.lat,
          lon: location.lng,
          radius: radius
        },
        timeout: 15000 // Set a 15 second timeout for the request
      });

      // Clear the timeout since the fetch completed
      clearTimeout(timeoutId);
      setFetchTimeout(null);

      if (response.data) {
        console.log('Received data:', response.data);
        
        // Normalize stop IDs - prefer the 14xxx format over 4xxx
        const normalizedStops = {};
        Object.entries(response.data).forEach(([stopId, stop]) => {
          // Make sure we're using the "id" format with the '1' prefix where appropriate
          const displayId = stop.gtfs_stop_id && stop.id ? stop.id : stopId;
          
          // Format IDs properly - ensure we have 14xxx format instead of 4xxx
          const formattedId = displayId.length === 4 && /^\d+$/.test(displayId) ? `1${displayId}` : displayId;
          
          // If we have both stop_id and gtfs_stop_id fields, use the longer one (likely 14xxx format)
          normalizedStops[formattedId] = {
            ...stop,
            id: formattedId, // Ensure id is consistent
            // For display purposes, ensure we show the full ID (14xxx) not the shortened one (4xxx)
            display_id: formattedId
          };
        });
        
        setNearbyStops(normalizedStops);
        
        const newMarkers = Object.entries(normalizedStops).map(([stopId, stop]) => ({
          position: {
            lat: parseFloat(stop.stop_lat),
            lng: parseFloat(stop.stop_lon)
          },
          title: stop.stop_name,
          stopId: stopId,
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
            },
            description: 'This is your current location. Click on the map to change it.'
          });
        }

        setMarkers(newMarkers);
        setError(null); // Clear any error messages
      }
    } catch (error) {
      console.error('Error fetching nearby stops:', error);
      if (error.response) {
        setError(`Stops could not be retrieved: ${error.response.data.detail || 'Unknown error'}`);
      } else if (error.request) {
        if (error.code === 'ECONNABORTED') {
          setError('Request timed out. The server is taking too long to respond. Please try again later.');
        } else {
          setError('Server connection failed. Please check your internet connection.');
        }
      } else {
        setError('Stops could not be retrieved. Please try again later.');
      }
    } finally {
      setFetchingStops(false);
      if (fetchTimeout) {
        clearTimeout(fetchTimeout);
        setFetchTimeout(null);
      }
    }
  };

  const handleMapClick = (event) => {
    const clickedLocation = {
      lat: event.latLng.lat(),
      lng: event.latLng.lng()
    };
    setUserLocation(clickedLocation);
    fetchNearbyStops(clickedLocation);
  };

  const handleAddressSearch = async () => {
    if (!searchAddress) return;
    try {
      setError(null);
      const formattedAddress = encodeURIComponent(`${searchAddress}, San Francisco, CA`);
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${formattedAddress}&limit=1`
      );
      const data = await response.json();
      if (data && data.length > 0) {
        const location = {
          lat: parseFloat(data[0].lat),
          lng: parseFloat(data[0].lon)
        };
        setUserLocation(location);
        fetchNearbyStops(location);
      } else {
        setError('Address not found in San Francisco. Please try a different address.');
      }
    } catch (error) {
      console.error('Error searching address:', error);
      setError('Failed to search address. Please try again.');
    }
  };

  const handleRadiusChange = (event, newValue) => {
    setRadius(newValue);
    if (userLocation) {
      fetchNearbyStops(userLocation);
    }
  };

  // Cleanup any pending timeouts when component unmounts
  useEffect(() => {
    return () => {
      if (fetchTimeout) {
        clearTimeout(fetchTimeout);
      }
    };
  }, [fetchTimeout]);

  return (
    <Container maxWidth="lg">
      <Box sx={{ my: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          MuniBuddy - SF Transit Finder
        </Typography>

        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        <Grid container spacing={2} sx={{ mb: 2 }}>
          <Grid item xs={12} md={6}>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <TextField
                fullWidth
                placeholder="Enter an address in San Francisco"
                value={searchAddress}
                onChange={(e) => setSearchAddress(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleAddressSearch()}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon />
                    </InputAdornment>
                  ),
                }}
              />
              <IconButton color="primary" onClick={requestLocation}>
                <MyLocationIcon />
              </IconButton>
              <Button variant="contained" onClick={handleAddressSearch} startIcon={<SearchIcon />}>
                Search
              </Button>
            </Box>
          </Grid>
          <Grid item xs={12} md={6}>
            <Box sx={{ px: 2 }}>
              <Typography gutterBottom>Search Radius: {radius} miles</Typography>
              <Slider
                value={radius}
                onChange={handleRadiusChange}
                min={0.1}
                max={1.0}
                step={0.05}
                marks={[{ value: 0.1, label: '0.1' }, { value: 0.5, label: '0.5' }, { value: 1.0, label: '1.0' }]}
                valueLabelDisplay="auto"
                valueLabelFormat={(value) => `${value} mi`}
              />
            </Box>
          </Grid>
        </Grid>

        <Paper elevation={3} sx={{ mb: 3, height: '400px', position: 'relative' }}>
          <Map
            center={userLocation || { lat: 37.7749, lng: -122.4194 }}
            markers={markers}
            onMapClick={handleMapClick}
            zoom={16}
          />
        </Paper>

        {fetchingStops && !error && (
          <Alert severity="info" sx={{ mb: 2 }}>
            <AlertTitle>Fetching Nearby Stops...</AlertTitle>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <CircularProgress size={20} sx={{ mr: 1 }} />
              <Typography>Looking for bus stops in this area. This may take a moment...</Typography>
            </Box>
          </Alert>
        )}

        {Object.keys(nearbyStops).length > 0 ? (
          <TransitInfo stops={nearbyStops} />
        ) : (
          <Typography variant="body1" color="text.secondary" align="center">
            {userLocation
              ? "No stops found nearby. Try a different location or increase the search radius."
              : "Select a location on the map to see nearby stops."}
          </Typography>
        )}
      </Box>

      <Dialog open={showLocationDialog} onClose={() => setShowLocationDialog(false)}>
        <DialogTitle>Enable Location Services</DialogTitle>
        <DialogContent>
          <Typography>
            Would you like to enable location services to find transit stops near you? You can also search for an address manually.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowLocationDialog(false)}>No, thanks</Button>
          <Button onClick={requestLocation} variant="contained" color="primary">Enable Location</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default App;