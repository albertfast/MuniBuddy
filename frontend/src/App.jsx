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
  CircularProgress // Import CircularProgress
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import MyLocationIcon from '@mui/icons-material/MyLocation';
import Map from './components/Map'; // Assuming Map component is in ./components/Map
import TransitInfo from './components/TransitInfo'; // Assuming TransitInfo component is in ./components/TransitInfo
// Import the geocodeAddress function
import { geocodeAddress, parseCoordinates, formatCoordinates } from './utility/geocode';

// Retrieve environment variables (will be replaced with actual values during build)
const BASE_URL = import.meta.env.VITE_API_BASE;
const GOOGLE_MAPS_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

// Log env vars during development/debugging (won't show in production build console unless specifically configured)
console.log("API Base URL:", BASE_URL);
console.log("Google Maps API Key Loaded:", !!GOOGLE_MAPS_KEY);

const App = () => {
  // State variables
  const [userLocation, setUserLocation] = useState(null); // { lat: number, lng: number } | null
  const [nearbyStops, setNearbyStops] = useState({}); // Stores the fetched stops data
  const [error, setError] = useState(null); // Stores any error message string
  const [markers, setMarkers] = useState([]); // Array of markers for the map
  const [searchAddress, setSearchAddress] = useState(''); // Input field value
  const [radius, setRadius] = useState(0.15); // Search radius in miles
  const [showLocationDialog, setShowLocationDialog] = useState(true); // Controls the initial location prompt
  const [isLoading, setIsLoading] = useState(false); // Loading state for fetching/geocoding

  // Function to request the user's current geolocation
  const requestLocation = () => {
    setShowLocationDialog(false); // Close dialog regardless of outcome
    if (navigator.geolocation) {
      setIsLoading(true); // Start loading indicator
      setError(null); // Clear previous errors
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const location = {
            lat: position.coords.latitude,
            lng: position.coords.longitude
          };
          console.log("Geolocation success:", location);
          setUserLocation(location);
          fetchNearbyStops(location); // Fetch stops for the current location
          // setIsLoading(false) will be handled by fetchNearbyStops' finally block
        },
        (err) => {
          console.error("Geolocation error:", err);
          setError('Could not get location. Please allow location access or enter manually.');
          setIsLoading(false); // Stop loading on error
        }
      );
    } else {
      setError('Geolocation is not supported by this browser.');
      setIsLoading(false); // Geolocation not supported
    }
  };

  // Function to fetch nearby stops from the backend API
  const fetchNearbyStops = async (location) => {
    if (!location) return;
    setIsLoading(true); // Start loading indicator
    setError(null); // Clear previous errors

    // Ensure BASE_URL is defined
    if (!BASE_URL) {
        console.error("API Base URL (VITE_API_BASE) is not defined!");
        setError("Application configuration error. Cannot fetch stops.");
        setIsLoading(false);
        return;
    }

    const url = `${BASE_URL}/nearby-stops?lat=${location.lat}&lon=${location.lng}&radius_miles=${radius}`;
    console.log("Fetching nearby stops:", url);

    try {
      const response = await fetch(url);
      if (!response.ok) {
        // Handle non-JSON error responses (like HTML error pages)
        const errorText = await response.text();
        console.error("Fetch error response:", response.status, errorText);
        throw new Error(`Failed to fetch stops: ${response.statusText} (Status: ${response.status})`);
      }

      const data = await response.json();
      console.log("Nearby stops data:", data);

      if (data && typeof data === 'object') {
        setNearbyStops(data);
        // Create markers for the map
        const newMarkers = Object.entries(data).map(([stopId, stop]) => ({
          position: {
            lat: parseFloat(stop.stop_lat),
            lng: parseFloat(stop.stop_lon)
          },
          title: stop.stop_name,
          stopId,
          icon: { // Define icon for bus stops
            url: '/images/bus-stop-icon.png', // Ensure this path is correct in your public folder
            scaledSize: { width: 32, height: 32 }
          }
        }));

        // Add marker for the user's current location
        if (userLocation) { // Use the state variable 'userLocation' which triggered this fetch
          newMarkers.push({
            position: userLocation,
            title: 'Your Location / Search Center',
            icon: { // Define icon for user location
              url: '/user-location-icon.svg', // Changed from .png to .svg
              scaledSize: { width: 32, height: 32 }
            }
          });
        }
        setMarkers(newMarkers);
      } else {
        setNearbyStops({});
        setMarkers(userLocation ? [{ // Only show user marker if stops are empty
            position: userLocation,
            title: 'Your Location / Search Center',
            icon: { url: '/user-location-icon.svg', scaledSize: { width: 32, height: 32 } }
        }] : []);
      }
    } catch (err) {
      console.error("Nearby stop fetch error:", err);
      setError(`Could not load nearby stops. ${err.message}`);
      setNearbyStops({}); // Clear stops on error
      setMarkers(userLocation ? [{ // Only show user marker on error
        position: userLocation,
        title: 'Your Location / Search Center',
        icon: { url: '/user-location-icon.svg', scaledSize: { width: 32, height: 32 } }
    }] : []);
    } finally {
      setIsLoading(false); // Stop loading indicator regardless of outcome
    }
  };

  // Handle clicks directly on the map to set a new location
  const handleMapClick = (event) => {
    const location = {
      lat: event.latLng.lat(),
      lng: event.latLng.lng()
    };
    console.log("Map clicked location:", location);
    setUserLocation(location); // Update user location state
    setSearchAddress(`${location.lat.toFixed(5)}, ${location.lng.toFixed(5)}`); // Update input field
    fetchNearbyStops(location); // Fetch stops for the clicked location
  };

  // Handle changes in the search radius slider
  const handleRadiusChange = (event, newValue) => {
    setRadius(newValue);
    // Refetch stops if a location is already set
    if (userLocation) {
      fetchNearbyStops(userLocation);
    }
  };

  // Handle search button click or Enter key press in the text field
  const handleManualLocationSearch = async () => {
    const input = searchAddress?.trim() || "";

    if (!input) {
      setError("Please enter coordinates or an address.");
      return;
    }

    setError(null);
    setIsLoading(true);

    // Check if input matches coordinate format
    const coordinates = parseCoordinates(input);

    if (coordinates) {
      // Valid coordinates
      setUserLocation(coordinates);
      fetchNearbyStops(coordinates);
      setIsLoading(false);
      return;
    }

    // Input is treated as an address
    try {
      console.log("Input treated as address. Attempting geocoding:", input);
      const data = await geocodeAddress(input);

      if (data && data.lat && data.lng) {
        const location = { lat: data.lat, lng: data.lng };
        setUserLocation(location);
        setSearchAddress(formatCoordinates(data.lat, data.lng));
        fetchNearbyStops(location);
      } else {
        setError(`Could not find coordinates for "${input}". Please try a more specific address.`);
      }
    } catch (err) {
      console.error("Geocoding failed:", err);
      setError(`Failed to find location: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Effect to ask for location permission only once on initial load
  useEffect(() => {
    // This effect runs only once after the component mounts
    // The dialog state handles the prompt
  }, []); // Empty dependency array means run only on mount


  // --- JSX Rendering ---
  return (
    <Container maxWidth="lg">
      <Box sx={{ my: 4 }}>
        {/* App Title */}
        <Typography variant="h1" component="h1" align="center" gutterBottom>
          MuniBuddy
        </Typography>

        {/* Error Alert Display */}
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {/* Input Controls Grid */}
        <Grid container spacing={2} sx={{ mb: 2, alignItems: 'center' }}>
          {/* Location Search Input */}
          <Grid item xs={12} md={6}>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <TextField
                fullWidth
                placeholder="Enter address or coordinates (lat, lon)"
                value={searchAddress}
                onChange={(e) => setSearchAddress(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleManualLocationSearch()}
                variant="outlined"
                size="small"
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon />
                    </InputAdornment>
                  )
                }}
                disabled={isLoading} // Disable input while loading
              />
              <IconButton
                color="primary"
                onClick={requestLocation}
                title="Use Current Location"
                disabled={isLoading}
              >
                <MyLocationIcon />
              </IconButton>
              <Button
                variant="contained"
                onClick={handleManualLocationSearch}
                disabled={isLoading} // Disable button while loading
                startIcon={isLoading ? <CircularProgress size={20} color="inherit" /> : <SearchIcon />}
              >
                {isLoading ? 'Searching...' : 'Search'}
              </Button>
            </Box>
          </Grid>

          {/* Radius Slider */}
          <Grid item xs={12} md={6}>
            <Box sx={{ px: { xs: 0, md: 2} }}> {/* Add some padding on medium screens */}
              <Typography id="radius-slider-label" gutterBottom>
                Search Radius: {radius} miles
              </Typography>
              <Slider
                aria-labelledby="radius-slider-label"
                value={radius}
                onChange={handleRadiusChange} // Use onChange for immediate feedback (optional: use onChangeCommitted)
                min={0.1}  
                max={1.0}
                step={0.05}
                marks={[
                  { value: 0.1, label: '0.1' },
                  { value: 0.5, label: '0.5' },
                  { value: 1.0, label: '1.0' }
                ]}
                valueLabelDisplay="auto"
                disabled={isLoading || !userLocation} // Disable if loading or no location set
              />
            </Box>
          </Grid>
        </Grid>

        {/* Map Display */}
        <Paper elevation={3} sx={{ height: '450px', position: 'relative', mb: 4, overflow: 'hidden' }}>
          <Map
            // Use userLocation if available, otherwise default SF center
            center={userLocation || { lat: 37.7749, lng: -122.4194 }}
            markers={markers} // Pass the generated markers
            onMapClick={handleMapClick} // Allow setting location by clicking map
            zoom={15} // Adjust initial/default zoom level as needed
          />
          {/* Optional: Loading overlay on map */}
          {isLoading && (
             <Box sx={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(255,255,255,0.5)', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                <CircularProgress />
             </Box>
          )}
        </Paper>

        {/* Transit Information Display */}
        {!isLoading && Object.keys(nearbyStops).length > 0 ? (
          <TransitInfo stops={nearbyStops} />
        ) : (
          !isLoading && !error && // Only show 'No stops found' if not loading and no error occurred
          <Typography align="center" color="textSecondary" sx={{ py: 3 }}>
            {userLocation ? 'No stops found nearby. Try increasing the radius or searching a different location.' : 'Enter a location or use current location to find stops.'}
          </Typography>
        )}

        {/* Initial Location Permission Dialog */}
        <Dialog
            open={showLocationDialog}
            onClose={() => setShowLocationDialog(false)} // Allow closing without choosing
            aria-labelledby="location-dialog-title"
        >
          <DialogTitle id="location-dialog-title">Use Your Location?</DialogTitle>
          <DialogContent>
            <Typography>
              Allow MuniBuddy to use your current location to automatically find nearby transit stops?
            </Typography>
          </DialogContent>
          <DialogActions>
            {/* Allow user to simply close the dialog */}
            <Button onClick={() => setShowLocationDialog(false)}>Maybe Later</Button>
            {/* Button to trigger location request */}
            <Button onClick={requestLocation} variant="contained" color="primary">
              Use Location
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </Container>
  );
};

export default App;