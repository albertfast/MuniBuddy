import React, { useState, useCallback, useEffect } from 'react';
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
  CircularProgress,
  Snackbar
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import MyLocationIcon from '@mui/icons-material/MyLocation';
import axios from 'axios';
import Map from './components/Map';
import TransitInfo from './components/TransitInfo';
// import { debounce } from 'lodash'; -- lodash kütüphanesini kaldırıyoruz

// Kendi debounce fonksiyonumuzu oluşturuyoruz
const debounce = (func, delay) => {
  let timeoutId;
  return (...args) => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => {
      func(...args);
    }, delay);
  };
};

// Add request caching and cancel token
const API_CACHE = {};
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes in milliseconds

const App = () => {
  const [userLocation, setUserLocation] = useState(null);
  const [nearbyStops, setNearbyStops] = useState({});
  const [error, setError] = useState(null);
  const [markers, setMarkers] = useState([]);
  const [searchAddress, setSearchAddress] = useState('');
  const [radius, setRadius] = useState(0.15);
  const [showLocationDialog, setShowLocationDialog] = useState(true);
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState({ open: false, message: '', severity: 'info' });

  // Create a debounced search function
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const debouncedFetchNearbyStops = useCallback(
    debounce((location) => {
      fetchNearbyStops(location);
    }, 500),
    []
  );

  const requestLocation = () => {
    setLoading(true);
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const location = {
            lat: position.coords.latitude,
            lng: position.coords.longitude
          };
          setUserLocation(location);
          debouncedFetchNearbyStops(location);
          setShowLocationDialog(false);
          setLoading(false);
        },
        (error) => {
          console.error('Error getting location:', error);
          setError('Please enable location services or enter an address manually.');
          setShowLocationDialog(false);
          setLoading(false);
          setNotification({
            open: true,
            message: 'Could not get your location. Please try searching for an address.',
            severity: 'warning'
          });
        }
      );
    } else {
      setError('Geolocation is not supported by your browser. Please enter an address manually.');
      setShowLocationDialog(false);
      setLoading(false);
      setNotification({
        open: true,
        message: 'Your browser does not support geolocation. Please search for an address.',
        severity: 'error'
      });
    }
  };

  const getCachedData = (key) => {
    const cachedItem = API_CACHE[key];
    if (cachedItem && (Date.now() - cachedItem.timestamp < CACHE_TTL)) {
      console.log('Using cached data for:', key);
      return cachedItem.data;
    }
    return null;
  };

  const setCachedData = (key, data) => {
    API_CACHE[key] = {
      data,
      timestamp: Date.now()
    };
  };

  const fetchNearbyStops = async (location) => {
    setLoading(true);
    try {
      setError(null);
      
      // Generate cache key
      const cacheKey = `stops_${location.lat.toFixed(6)}_${location.lng.toFixed(6)}_${radius}`;
      
      // Check cache first
      const cachedData = getCachedData(cacheKey);
      if (cachedData) {
        setNearbyStops(cachedData);
        updateMarkers(cachedData, location);
        setLoading(false);
        return;
      }
      
      // If not in cache, fetch from API
      const startTime = performance.now();
      // API URL yapısını düzeltiyoruz - /api/api/ sorunu için çözüm
      const apiBaseUrl = import.meta.env.VITE_API_BASE || '/api';
      const response = await axios.get(`${apiBaseUrl}/nearby-stops`, {
        params: {
          lat: location.lat,
          lon: location.lng,
          radius_miles: radius
        },
        timeout: 10000 // 10 second timeout
      });
      const endTime = performance.now();
      console.log(`API request took ${endTime - startTime}ms`);

      if (response.data) {
        // Cache the response
        setCachedData(cacheKey, response.data);
        
        setNearbyStops(response.data);
        updateMarkers(response.data, location);
      }
    } catch (error) {
      console.error('Error fetching nearby stops:', error);
      if (error.response) {
        // Server error response
        setError(`Could not get stops: ${error.response.data.detail || 'Unknown error'}`);
        setNotification({
          open: true,
          message: 'Server error. Please try again later.',
          severity: 'error'
        });
      } else if (error.request) {
        // No response received
        setError('Could not connect to server. Please check your internet connection.');
        setNotification({
          open: true,
          message: 'Connection error. Please check your internet and try again.',
          severity: 'error'
        });
      } else {
        // Request setup error
        setError('Could not get stops. Please try again later.');
        setNotification({
          open: true,
          message: 'An error occurred. Please try again.',
          severity: 'error'
        });
      }
    } finally {
      setLoading(false);
    }
  };

  const updateMarkers = (stopsData, location) => {
    const newMarkers = Object.entries(stopsData).map(([stopId, stop]) => ({
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

    if (location) {
      newMarkers.push({
        position: location,
        title: 'Your Location',
        icon: {
          url: '/images/user-location-icon.png',
          scaledSize: { width: 32, height: 32 }
        }
      });
    }

    setMarkers(newMarkers);
  };

  const handleMapClick = (event) => {
    const clickedLocation = {
      lat: event.latLng.lat(),
      lng: event.latLng.lng()
    };
    setUserLocation(clickedLocation);
    debouncedFetchNearbyStops(clickedLocation);
  };

  const handleAddressSearch = async () => {
    if (!searchAddress.trim()) {
      setNotification({
        open: true,
        message: 'Please enter an address to search',
        severity: 'info'
      });
      return;
    }
    
    setLoading(true);
    try {
      setError(null);
      const cacheKey = `address_${searchAddress.toLowerCase().trim()}`;
      
      // Check cache first
      const cachedLocation = getCachedData(cacheKey);
      if (cachedLocation) {
        setUserLocation(cachedLocation);
        debouncedFetchNearbyStops(cachedLocation);
        setLoading(false);
        return;
      }
      
      const formattedAddress = encodeURIComponent(`${searchAddress}, San Francisco, CA`);
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${formattedAddress}&limit=1`,
        { timeout: 5000 }
      );

      const data = await response.json();
      if (data && data.length > 0) {
        const location = {
          lat: parseFloat(data[0].lat),
          lng: parseFloat(data[0].lon)
        };
        
        // Cache the location
        setCachedData(cacheKey, location);
        
        setUserLocation(location);
        debouncedFetchNearbyStops(location);
      } else {
        setError('Address not found in San Francisco. Please try a different address.');
        setNotification({
          open: true,
          message: 'Address not found. Try a more specific address in San Francisco.',
          severity: 'warning'
        });
      }
    } catch (error) {
      console.error('Error searching address:', error);
      setError('Failed to search address. Please try again.');
      setNotification({
        open: true,
        message: 'Error searching address. Please check your connection and try again.',
        severity: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  // Execute search when user presses Enter
  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleAddressSearch();
    }
  };

  const handleRadiusChange = (event, newValue) => {
    setRadius(newValue);
    if (userLocation) {
      debouncedFetchNearbyStops(userLocation);
    }
  };

  const handleNotificationClose = () => {
    setNotification({ ...notification, open: false });
  };

  useEffect(() => {
    // Clean up debounce on component unmount
    return () => {
      debouncedFetchNearbyStops.cancel();
    };
  }, [debouncedFetchNearbyStops]);

  return (
    <Container maxWidth="lg">
      <Box sx={{ my: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
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
                placeholder="Enter an address in San Francisco"
                value={searchAddress}
                onChange={(e) => setSearchAddress(e.target.value)}
                onKeyPress={handleKeyPress}
                disabled={loading}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon />
                    </InputAdornment>
                  ),
                }}
                sx={{
                  '& .MuiOutlinedInput-root': {
                    backgroundColor: 'background.paper',
                    '&:hover': {
                      '& > fieldset': {
                        borderColor: 'primary.main',
                      },
                    },
                  },
                }}
              />
              <IconButton 
                color="primary" 
                onClick={requestLocation}
                disabled={loading}
                sx={{ bgcolor: 'background.paper' }}
              >
                <MyLocationIcon />
              </IconButton>
              <Button 
                variant="contained" 
                onClick={handleAddressSearch}
                startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <SearchIcon />}
                disabled={loading || !searchAddress.trim()}
              >
                {loading ? 'Searching...' : 'Search'}
              </Button>
            </Box>
          </Grid>
          <Grid item xs={12} md={6}>
            <Box sx={{ px: 2 }}>
              <Typography gutterBottom>
                Search Radius: {radius} miles
              </Typography>
              <Slider
                value={radius}
                onChange={handleRadiusChange}
                min={0.1}
                max={1.0}
                step={0.05}
                marks={[
                  { value: 0.1, label: '0.1' },
                  { value: 0.5, label: '0.5' },
                  { value: 1.0, label: '1.0' },
                ]}
                valueLabelDisplay="auto"
                valueLabelFormat={(value) => `${value} mi`}
                disabled={loading}
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
          {loading && (
            <Box 
              sx={{ 
                position: 'absolute', 
                top: 0, 
                left: 0, 
                right: 0, 
                bottom: 0, 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                backgroundColor: 'rgba(255, 255, 255, 0.7)',
                zIndex: 10
              }}
            >
              <Box sx={{ textAlign: 'center' }}>
                <CircularProgress size={50} />
                <Typography variant="body2" sx={{ mt: 2 }}>Loading transit data...</Typography>
              </Box>
            </Box>
          )}
        </Paper>

        {Object.keys(nearbyStops).length > 0 ? (
          <TransitInfo stops={nearbyStops} />
        ) : (
          <Typography variant="body1" color="textSecondary" align="center">
            No transit stops found nearby. Try a different location or increase the search radius.
          </Typography>
        )}
      </Box>

      <Dialog open={showLocationDialog} onClose={() => setShowLocationDialog(false)}>
        <DialogTitle>Enable Location Services</DialogTitle>
        <DialogContent>
          <Typography>
            Would you like to enable location services to find transit stops near you? 
            You can also search for an address manually.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowLocationDialog(false)}>
            No, thanks
          </Button>
          <Button 
            onClick={requestLocation} 
            variant="contained" 
            color="primary"
            disabled={loading}
            startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <LocationOnIcon />}
          >
            {loading ? 'Getting Location...' : 'Enable Location'}
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={notification.open}
        autoHideDuration={6000}
        onClose={handleNotificationClose}
        message={notification.message}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert 
          onClose={handleNotificationClose} 
          severity={notification.severity} 
          variant="filled"
          sx={{ width: '100%' }}
        >
          {notification.message}
        </Alert>
      </Snackbar>
    </Container>
  );
};

export default App;
