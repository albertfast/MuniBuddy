// frontend/src/App.jsx
import React, { useState, useEffect, useCallback } from 'react';
import {
  Container, Box, Typography, Alert, TextField, InputAdornment,
  Slider, Grid, Button, Dialog, DialogTitle, DialogContent, DialogActions,
  CircularProgress, Paper // Import Paper for the sticky top panel
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import MyLocationIcon from '@mui/icons-material/MyLocation';
import Map from './components/Map'; // Use the version that renders the logo as a control
import TransitInfo from './components/TransitInfo';
import { geocodeAddress, parseCoordinates, formatCoordinates } from './utility/geocode';
import './assets/style.css'; // Import global styles

// --- Constants ---
const BASE_URL = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api/v1'; // API Base URL
const DEFAULT_CENTER = { lat: 37.7749, lng: -122.4194 }; // Default map center

// --- Helper Functions ---

// Get a canonical (standardized) ID for BART stations for de-duplication
const getCanonicalBartId = (stop) => {
  if (stop.agency?.toLowerCase() !== 'bart' && stop.agency?.toLowerCase() !== 'ba') {
    return stop.stop_id; // Return original ID if not BART
  }
  // Derive base ID from stop_code or stop_id (e.g., POWL_7 -> POWL)
  let idPart = (stop.stop_code || stop.stop_id || '').split('_')[0].toUpperCase();
  // Handle 'place_' prefix
  if (idPart.startsWith('PLACE-')) { idPart = idPart.substring(6); }
  else if (idPart.startsWith('PLACE_')) { idPart = idPart.substring(6); }

  // Check against known main station codes first
  const knownMainStationCodes = ['POWL', 'MONT', 'EMBR', 'CIVC', 'DALY', 'GLEN', 'BALB', 'COLM', 'SSAN', 'SBRN', 'SFIA', 'MLBR'];
  if (knownMainStationCodes.includes(idPart)) {
    return idPart;
  }
  // Fallback: Check stop_name
  const name = stop.stop_name?.toLowerCase() || '';
  if (name.includes('powell street')) return 'POWL';
  if (name.includes('montgomery st')) return 'MONT';
  if (name.includes('embarcadero')) return 'EMBR';
  if (name.includes('civic center') || name.includes('civic ctr')) return 'CIVC';
  // Add more name mappings if needed

  // Final fallback
  return idPart || (stop.stop_id || 'UNKNOWN_BART').toUpperCase();
};

// --- Main App Component ---
const App = () => {
  // --- State ---
  const [userLocation, setUserLocation] = useState(null); // Current location {lat, lng}
  const [nearbyStops, setNearbyStops] = useState({}); // Processed stops for TransitInfo { displayKey: stopObject }
  const [error, setError] = useState(null); // Error messages
  const [markers, setMarkers] = useState([]); // Markers for the Map component
  const [liveVehicleMarkers, setLiveVehicleMarkers] = useState([]); // Live vehicle markers (optional)
  const [searchAddress, setSearchAddress] = useState(''); // Search input value
  const [radius, setRadius] = useState(0.15); // Search radius
  const [isLoading, setIsLoading] = useState(false); // Loading state indicator
  const [theme, setTheme] = useState('system'); // Theme state ('light', 'dark', 'system')
  const [showLocationDialog, setShowLocationDialog] = useState(true); // Initial location prompt visibility

  // --- Effects ---
  // Load theme from localStorage on mount
  useEffect(() => {
    const storedTheme = localStorage.getItem('theme') || 'system';
    setTheme(storedTheme);
    document.documentElement.setAttribute('data-theme', storedTheme);
  }, []);

  // Fetch stops when location or radius changes
  useEffect(() => {
    if (userLocation) {
      fetchNearbyStops(userLocation);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userLocation, radius]); // fetchNearbyStops is memoized

  // --- Callbacks ---
  // Toggle theme
  const toggleTheme = () => {
    let newTheme = theme === 'light' ? 'dark' : (theme === 'dark' ? 'system' : 'light');
    setTheme(newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
  };

  // Get text for theme button
  const getThemeButtonText = () => {
    if (theme === 'light') return 'Switch to Dark Theme';
    if (theme === 'dark') return 'Use System Setting';
    return 'Switch to Light Theme';
  };

  // Request geolocation
  const requestLocation = useCallback(() => {
    setShowLocationDialog(false);
    if (navigator.geolocation) {
      setIsLoading(true);
      setError(null);
      navigator.geolocation.getCurrentPosition(
        pos => {
          const loc = { lat: pos.coords.latitude, lng: pos.coords.longitude };
          setUserLocation(loc); // Triggers fetch via useEffect
          setSearchAddress(formatCoordinates(loc.lat, loc.lng));
        },
        err => {
          setError(`Location access denied: ${err.message}. Search manually.`);
          setIsLoading(false);
        }
      );
    } else {
      setError('Geolocation not supported.');
      setIsLoading(false);
    }
  }, []);

  // Fetch nearby stops from API
  const fetchNearbyStops = useCallback(async (location) => {
    if (!location) return;
    setIsLoading(true);
    setError(null);
    const processedStopsForDisplay = {};
    const addedBartCanonicalIds = new Set();

    try {
      const apiUrl = `${BASE_URL}/nearby-stops?lat=${location.lat}&lon=${location.lng}&radius=${radius}`;
      const res = await fetch(apiUrl);
      if (!res.ok) throw new Error(`API error (${res.status}): ${await res.text()}`);
      const rawStopsFromApi = await res.json();

      // Step 1: De-duplicate stops from API based on original stop_id
      const uniqueStopsById = {};
      for (const stop of rawStopsFromApi) {
        if (stop.stop_id != null && !uniqueStopsById[stop.stop_id]) {
          uniqueStopsById[stop.stop_id] = stop;
        }
      }
      const uniqueRawStopsList = Object.values(uniqueStopsById);

      // Step 2: Process unique stops, handle BART canonicalization and prioritization
      for (const stop of uniqueRawStopsList) {
        const agency = stop.agency?.toLowerCase();
        let displayKey;
        let stopDataToProcess = { ...stop };

        if (agency === 'bart' || agency === 'ba') {
          const canonicalId = getCanonicalBartId(stop);
          displayKey = canonicalId;
          // Check if this stop represents the main station (e.g., name includes "Street")
          const isCurrentStopMainStation = stop.stop_name?.toLowerCase().includes('street'); // Define *before* using it

          if (addedBartCanonicalIds.has(canonicalId)) { // If we already processed this BART station
            const existingStop = processedStopsForDisplay[canonicalId];
            const isExistingStopMainStation = existingStop?.stop_name?.toLowerCase().includes('street');

            // If current is main station and existing was not, we will overwrite (let code proceed)
            // Otherwise (if existing was main, or both are not), skip the current one.
            if (!isCurrentStopMainStation || isExistingStopMainStation) {
              continue; // Skip this stop
            }
            // console.log(`[App] Replacing BART entrance '${existingStop.stop_name}' with main station '${stop.stop_name}'`);
          } else {
            // First time seeing this canonical ID
            addedBartCanonicalIds.add(canonicalId);
          }

          // Prepare data for TransitInfo
          stopDataToProcess.display_id_for_transit_info = stop.stop_code || canonicalId; // ID for API calls in TransitInfo
          stopDataToProcess.original_stop_id_for_key = stop.stop_id; // For React key prop
        } else { // For non-BART agencies
          displayKey = stop.stop_id || `${stop.stop_code}-${agency}`;
          stopDataToProcess.display_id_for_transit_info = stop.stop_code || stop.stop_id;
          stopDataToProcess.original_stop_id_for_key = stop.stop_id;
        }

        // Add or update the stop in the final display list
        processedStopsForDisplay[displayKey] = stopDataToProcess;
      }

      setNearbyStops(processedStopsForDisplay); // Update state

      // Create map markers
      const stopMarkersArr = Object.values(processedStopsForDisplay).map(s => ({
        position: { lat: parseFloat(s.stop_lat), lng: parseFloat(s.stop_lon) },
        title: s.stop_name,
        stopId: s.display_id_for_transit_info, // ID matching what TransitInfo uses
        icon: {
          url: (s.agency?.toLowerCase() === 'bart' || s.agency?.toLowerCase() === 'ba') ? '/images/bart-station-icon.svg' : '/images/bus-stop-icon.svg',
          scaledSize: { width: 28, height: 28 }
        }
      }));

      // Add user location marker
      if (userLocation) {
        stopMarkersArr.push({
          position: userLocation, title: 'You Are Here', stopId: 'user-location',
          icon: { url: '/images/user-location-icon.svg', scaledSize: { width: 30, height: 30 } }
        });
      }
      setMarkers(stopMarkersArr);

    } catch (err) { // Handle fetch/processing errors
      console.error('Could not fetch or process nearby stops:', err);
      setError(`Could not fetch stops: ${err.message}`);
      setNearbyStops({}); // Clear stops
      setMarkers(userLocation ? [{ // Keep only user marker
        position: userLocation, title: 'You Are Here', stopId: 'user-location',
        icon: { url: '/images/user-location-icon.svg', scaledSize: { width: 30, height: 30 } }
      }] : []);
    } finally {
      setIsLoading(false); // Always reset loading state
    }
  }, [radius, BASE_URL]); // Dependencies

  // Handle manual search button click
  const handleManualLocationSearch = useCallback(async () => {
    const input = searchAddress.trim();
    if (!input) { setError('Please enter address or coordinates.'); return; }
    setIsLoading(true); setError(null);
    const coords = parseCoordinates(input);
    if (coords) { setUserLocation(coords); return; } // Let useEffect trigger fetch
    try {
      const data = await geocodeAddress(input);
      if (data?.lat && data?.lng) { setUserLocation({ lat: data.lat, lng: data.lng }); }
      else { setError('Address not found.'); setIsLoading(false); }
    } catch (err) { setError(`Geocoding error: ${err.message}`); setIsLoading(false); }
  }, [searchAddress]);

  // --- Render ---
  return (
    <Box className="overall-layout">

      {/* Map Area */}
      <Box maxWidth="lg" className="main-content-scrollable-area">
            {/* Hide Theme Switch Button
              <Button onClick={toggleTheme} variant="outlined" size="small" sx={{ textTransform: 'none', color: 'var(--purple)', borderColor: 'var(--purple)', '&:hover': { backgroundColor: 'var(--purpleLight)' } }}>
              {getThemeButtonText()}
            </Button>*/}        
        <Map
            center={userLocation || DEFAULT_CENTER}
            markers={markers}
            onMapClick={(e) => {
              const location = { lat: e.latLng.lat(), lng: e.latLng.lng() };
              setUserLocation(location);
              setSearchAddress(formatCoordinates(location.lat, location.lng));
            }}
          // showLogoOnMap={true} // Pass prop to Map if logo rendering is conditional
          />
          {/* Loading Overlay */}
          {isLoading && (
            <Box sx={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(var(--current-bg-color-rgb, 255,255,255),0.6)', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', zIndex: 10, borderRadius: 'inherit' }}>
              <CircularProgress />
              <Typography sx={{ mt: 1, color: 'var(--current-text-color)' }}>Loading map & stops...</Typography>
            </Box>
          )}
      </Box>

      {/* Right Panel */} 
        <Container maxWidth="lg" className="right-panel" sx={{ display: 'flex', flexDirection: 'column', pt: 1, pb: 1 }}>
          {/* Controls Row */}
          <Grid container className="searchbar_inner">
            {/* Locate Me Button */}
            <Grid item>
              <Button variant="outlined" onClick={requestLocation} startIcon={<MyLocationIcon />} disabled={isLoading && !userLocation && !searchAddress} size="medium">
                <span class="hidden">Locate Me</span>
              </Button>
            </Grid>
            {/* Search Input */}
            <Grid item className="searchbar_location">
              <TextField fullWidth placeholder="Starting Location" value={searchAddress}
                onChange={(e) => setSearchAddress(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleManualLocationSearch()}
                InputProps={{ startAdornment: (<InputAdornment position="start"><SearchIcon sx={{ color: 'var(--current-grayMid-val)' }} /></InputAdornment>) }}
                variant="outlined" size="small"
              />
            </Grid>
            {/* Search Button */}
            <Grid item>
              <Button variant="contained" onClick={handleManualLocationSearch} disabled={isLoading} size="medium">
                {isLoading && searchAddress ? <CircularProgress size={20} color="inherit" /> : "Search"}
              </Button>
            </Grid>
            {/* Radius Slider */}
            <Grid item xs={12} sx={{ display: 'flex', alignItems: 'center', mt: 0.5 }}>
              <Typography sx={{ mr: 1.5, fontSize: '0.85rem', color: 'var(--current-grayMid-val)' }}>Radius:</Typography>
              <Slider value={radius} min={0.1} max={1.0} step={0.05} onChange={(e, v) => setRadius(v)}
                valueLabelDisplay="auto" valueLabelFormat={(value) => `${value.toFixed(2)} mi`}
                size="small" sx={{ flexGrow: 1, maxWidth: '250px' }}
              />
              <Typography sx={{ ml: 1.5, fontSize: '0.85rem', color: 'var(--current-text-color)', minWidth: '45px', textAlign: 'right' }}>{radius.toFixed(2)} mi</Typography>
            </Grid>
          </Grid>
          {error && <Alert severity="error" sx={{ mt: 1, mb: 1 }} onClose={() => setError(null)}>{error}</Alert>}
          {/* Transit Info Panel */}
          <Grid item xs={12} md={5} lg={4} className="transit-info-panel-dynamic-height">
            {(isLoading && Object.keys(nearbyStops).length === 0) ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', minHeight: '200px' }}>
                {/* Optional placeholder/loader */}
              </Box>
            ) : Object.keys(nearbyStops).length > 0 ? (
              <TransitInfo stops={nearbyStops} setLiveVehicleMarkers={setLiveVehicleMarkers} baseApiUrl={BASE_URL} />
            ) : (
              !isLoading && (
                <Typography align="center" color="text.secondary" sx={{ py: 3, height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {userLocation ? 'No nearby stops found.' : 'Use "Locate Me" or search.'}
                </Typography>
              )
            )}
          </Grid>
        </Container>
      

      {/* Initial Location Dialog */}
      <Dialog open={showLocationDialog && !userLocation} onClose={() => setShowLocationDialog(false)}>
        <DialogTitle>Use Your Location?</DialogTitle>
        <DialogContent><Typography>Allow MuniBuddy to use your current location?</Typography></DialogContent>
        <DialogActions>
          <Button onClick={() => setShowLocationDialog(false)}>No Thanks</Button>
          <Button onClick={requestLocation} variant="contained">Use Location</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default App;