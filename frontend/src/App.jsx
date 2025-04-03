const BASE_URL = import.meta.env.VITE_API_BASE;

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
import LocationOnIcon from '@mui/icons-material/LocationOn';
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
       const response = await axios.get(`${BASE_URL}/nearby-stops`, {
        params: {
          lat: location.lat,
          lon: location.lng,
          radius_miles: radius
        }
      });

      if (response.data) {
        setNearbyStops(response.data);
        const newMarkers = Object.entries(response.data).map(([stopId, stop]) => ({
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
            }
          });
        }

        setMarkers(newMarkers);
      }
    } catch (error) {
      console.error('Error fetching nearby stops:', error);
      if (error.response) {
        // Sunucudan hata yanıtı geldi
        setError(`Duraklar alınamadı: ${error.response.data.detail || 'Bilinmeyen hata'}`);
      } else if (error.request) {
        // İstek yapıldı ama yanıt alınamadı
        setError('Sunucuya bağlanılamadı. Lütfen internet bağlantınızı kontrol edin.');
      } else {
        // İstek oluşturulurken hata oluştu
        setError('Duraklar alınamadı. Lütfen daha sonra tekrar deneyin.');
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
                onKeyPress={(e) => e.key === 'Enter' && handleAddressSearch()}
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
                sx={{ bgcolor: 'background.paper' }}
              >
                <MyLocationIcon />
              </IconButton>
              <Button 
                variant="contained" 
                onClick={handleAddressSearch}
                startIcon={<SearchIcon />}
              >
                Search
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
          <Button onClick={requestLocation} variant="contained" color="primary">
            Enable Location
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default App;
