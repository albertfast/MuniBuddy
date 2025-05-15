// frontend/src/App.jsx
import React, { useState, useEffect, useCallback, useMemo } from 'react';
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
import './assets/style.css';

const BASE_URL = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api/v1';
const DEFAULT_CENTER = { lat: 37.7749, lng: -122.4194 };

const getCanonicalBartId = (stop) => {
  if (stop.agency?.toLowerCase() !== 'bart' && stop.agency?.toLowerCase() !== 'ba') {
    return stop.stop_id;
  }
  let idPart = (stop.stop_code || stop.stop_id || '').split('_')[0].toUpperCase();
  if (idPart.startsWith('PLACE-')) { idPart = idPart.substring(6); }
  else if (idPart.startsWith('PLACE_')) { idPart = idPart.substring(6); }

  const knownMainStationCodes = ['POWL', 'MONT', 'EMBR', 'CIVC', 'DALY', 'GLEN', 'BALB', 'COLM', 'SSAN', 'SBRN', 'SFIA', 'MLBR'];
  if (knownMainStationCodes.includes(idPart)) return idPart;

  const name = stop.stop_name?.toLowerCase() || '';
  if (name.includes('powell street')) return 'POWL';
  if (name.includes('montgomery st')) return 'MONT';
  if (name.includes('embarcadero')) return 'EMBR';
  if (name.includes('civic center') || name.includes('civic ctr')) return 'CIVC';
  // Add more specific name mappings if necessary
  return idPart || `BART_${(stop.stop_id || 'UNKNOWN')}`.toUpperCase(); // Fallback with prefix
};

const App = () => {
  const [userLocation, setUserLocation] = useState(null);
  const [nearbyStops, setNearbyStops] = useState({});
  const [error, setError] = useState(null);
  const [markers, setMarkers] = useState([]);
  // const [liveVehicleMarkers, setLiveVehicleMarkers] = useState([]); // Kept if needed by TransitInfo
  const [searchAddress, setSearchAddress] = useState('');
  const [radius, setRadius] = useState(0.15);
  const [isLoading, setIsLoading] = useState(false);
  const [theme, setTheme] = useState('system');
  const [showLocationDialog, setShowLocationDialog] = useState(true);

  useEffect(() => {
    const storedTheme = localStorage.getItem('theme') || 'system';
    setTheme(storedTheme);
    document.documentElement.setAttribute('data-theme', storedTheme);
  }, []);

  const fetchNearbyStops = useCallback(async (location, currentRadius) => {
    if (!location) return;
    setIsLoading(true);
    setError(null);
    
    try {
      const apiUrl = `${BASE_URL}/nearby-stops?lat=${location.lat}&lon=${location.lng}&radius=${currentRadius}`;
      const res = await fetch(apiUrl);
      if (!res.ok) throw new Error(`API error (${res.status}): ${await res.text()}`);
      const rawStopsFromApi = await res.json();

      const processedStops = {};
      const addedBartCanonicalIds = new Set();

      for (const stop of rawStopsFromApi) {
        if (stop.stop_id == null && stop.stop_code == null) continue; // Skip stops with no identifier

        let displayKey;
        let stopDataForTransitInfo = { 
            ...stop, 
            original_stop_id_for_key: stop.stop_id || `${stop.agency}-${stop.stop_code}` // Stable key for React
        };
        const agency = stop.agency?.toLowerCase();

        if (agency === 'bart' || agency === 'ba') {
          const canonicalId = getCanonicalBartId(stop);
          displayKey = `BART_${canonicalId}`; // Ensure BART keys are distinct
          
          const isCurrentStopMainStation = stop.stop_name?.toLowerCase().includes('street');

          if (addedBartCanonicalIds.has(canonicalId)) {
            const existingStop = processedStops[displayKey];
            const isExistingStopMainStation = existingStop?.stop_name?.toLowerCase().includes('street');
            if (isExistingStopMainStation && !isCurrentStopMainStation) {
              continue; // Prefer existing main station entry
            }
          }
          addedBartCanonicalIds.add(canonicalId);
          stopDataForTransitInfo.display_id_for_transit_info = canonicalId; // Clean ID for API calls
          stopDataForTransitInfo.stop_code_for_display = canonicalId; // Use canonical for display ID too
        } else {
          displayKey = stop.stop_id || `${agency}-${stop.stop_code}`;
          stopDataForTransitInfo.display_id_for_transit_info = stop.stop_code || stop.stop_id;
          stopDataForTransitInfo.stop_code_for_display = stop.stop_code || stop.stop_id;
        }
        
        processedStops[displayKey] = stopDataForTransitInfo;
      }
      
      setNearbyStops(processedStops);

      const stopMarkersArr = Object.values(processedStops).map(s => ({
        position: { lat: parseFloat(s.stop_lat), lng: parseFloat(s.stop_lon) },
        title: s.stop_name,
        stopId: s.display_id_for_transit_info, // Consistent ID
        agency: s.agency, // Pass agency for icon selection
        icon: {
          url: (s.agency?.toLowerCase() === 'bart' || s.agency?.toLowerCase() === 'ba') ? '/images/bart-station-icon.svg' : '/images/bus-stop-icon.svg',
          scaledSize: { width: 28, height: 28 }
        }
      }));

      if (userLocation) {
        stopMarkersArr.push({
          position: userLocation, title: 'You Are Here', stopId: 'user-location',
          icon: { url: '/images/user-location-icon.svg', scaledSize: { width: 30, height: 30 } }
        });
      }
      setMarkers(stopMarkersArr);

    } catch (err) {
      console.error('Could not fetch or process nearby stops:', err);
      setError(`Could not fetch stops: ${err.message}`);
      setNearbyStops({});
      setMarkers(userLocation ? [{
        position: userLocation, title: 'You Are Here', stopId: 'user-location',
        icon: { url: '/images/user-location-icon.svg', scaledSize: { width: 30, height: 30 } }
      }] : []);
    } finally {
      setIsLoading(false);
    }
  }, [userLocation, BASE_URL]); // Removed radius from here, pass it directly

  useEffect(() => {
    if (userLocation) {
      fetchNearbyStops(userLocation, radius);
    }
  }, [userLocation, radius, fetchNearbyStops]);


  const requestLocation = useCallback(() => {
    setShowLocationDialog(false);
    if (navigator.geolocation) {
      setIsLoading(true); setError(null);
      navigator.geolocation.getCurrentPosition(
        pos => {
          const loc = { lat: pos.coords.latitude, lng: pos.coords.longitude };
          setUserLocation(loc);
          setSearchAddress(formatCoordinates(loc.lat, loc.lng));
        },
        err => {
          setError(`Location access denied: ${err.message}. Search manually.`);
          setIsLoading(false);
        },
        { timeout: 10000 } // Added timeout for geolocation
      );
    } else {
      setError('Geolocation not supported.'); setIsLoading(false);
    }
  }, []);

  const handleManualLocationSearch = useCallback(async () => {
    const input = searchAddress.trim();
    if (!input) { setError('Please enter address or coordinates.'); return; }
    setIsLoading(true); setError(null);
    const coords = parseCoordinates(input);
    if (coords) {
      setUserLocation(coords); // This will trigger fetchNearbyStops via useEffect
      // setIsLoading(false); // fetchNearbyStops will handle this
      return;
    }
    try {
      const data = await geocodeAddress(input);
      if (data?.lat && data?.lng) {
        setUserLocation({ lat: data.lat, lng: data.lng }); // Triggers fetch
      } else {
        setError('Address not found.'); setIsLoading(false);
      }
    } catch (err) {
      setError(`Geocoding error: ${err.message}`); setIsLoading(false);
    }
  }, [searchAddress]);
  
  // Memoize stops for TransitInfo to prevent unnecessary re-renders if props object reference changes but content is same
  const memoizedStops = useMemo(() => nearbyStops, [nearbyStops]);

  return (
    <Box className="overall-layout">
      <Box className="map-area" sx={{ backgroundColor: 'var(--current-grayLight2-val)' }}> {/* Added a subtle bg to map area for contrast */}
        <Map
          center={userLocation || DEFAULT_CENTER}
          markers={markers}
          onMapClick={(e) => {
            const location = { lat: e.latLng.lat(), lng: e.latLng.lng() };
            setUserLocation(location);
            setSearchAddress(formatCoordinates(location.lat, location.lng));
          }}
        />
        {isLoading && (
          <Box sx={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(var(--current-bg-color-rgb, 255,255,255),0.7)', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', zIndex: 10, borderRadius: 'inherit' }}>
            <CircularProgress />
            <Typography sx={{ mt: 1.5, color: 'var(--current-text-color)' }}>Loading...</Typography>
          </Box>
        )}
      </Box>

      <Box className="right-panel-container">
        <Box className="controls-panel">
          <Grid container spacing={1} alignItems="center" className="searchbar_inner">
            <Grid item>
              <Button variant="outlined" onClick={requestLocation} disabled={isLoading && !userLocation && !searchAddress} size="medium" aria-label="Locate Me">
                <MyLocationIcon />
                <span className="hidden">Locate Me</span>
              </Button>
            </Grid>
            <Grid item xs className="searchbar_location">
              <TextField fullWidth placeholder="Address or Coordinates" value={searchAddress}
                onChange={(e) => setSearchAddress(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleManualLocationSearch()}
                InputProps={{ startAdornment: (<InputAdornment position="start"><SearchIcon sx={{ color: 'var(--current-grayMid-val)' }} /></InputAdornment>) }}
                variant="outlined" size="small"
              />
            </Grid>
            <Grid item>
              <Button variant="contained" onClick={handleManualLocationSearch} disabled={isLoading} size="medium">
                {isLoading && searchAddress ? <CircularProgress size={20} color="inherit" /> : "Search"}
              </Button>
            </Grid>
          </Grid>
          <Box className="radius-controls">
              <Typography>Radius:</Typography>
              <Slider value={radius} min={0.1} max={1.0} step={0.05} onChange={(e, v) => setRadius(v)}
                valueLabelDisplay="auto" valueLabelFormat={(value) => `${value.toFixed(2)} mi`}
                size="small" aria-labelledby="radius-slider-label"
              />
              <Typography>{radius.toFixed(2)} mi</Typography>
          </Box>
        </Box>

        {error && <Alert severity="error" sx={{ mt: 1, mb: 1 }} onClose={() => setError(null)}>{error}</Alert>}
        
        <Box className="transit-info-panel">
          {(isLoading && Object.keys(memoizedStops).length === 0 && !error) ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', minHeight: '200px' }}>
              {/* Placeholder while initial stops load, distinct from map loading */}
            </Box>
          ) : Object.keys(memoizedStops).length > 0 ? (
            <TransitInfo stops={memoizedStops} /* setLiveVehicleMarkers={setLiveVehicleMarkers} */ baseApiUrl={BASE_URL} />
          ) : (
            !isLoading && !error && (
              <Typography align="center" color="text.secondary" sx={{ py: 3, height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {userLocation ? 'No nearby stops found for this location and radius.' : 'Use "Locate Me" or search for a location.'}
              </Typography>
            )
          )}
        </Box>
      </Box>

      <Dialog open={showLocationDialog && !userLocation} onClose={() => setShowLocationDialog(false)}>
        <DialogTitle>Use Your Location?</DialogTitle>
        <DialogContent><Typography>Allow MuniBuddy to use your current location to find nearby transit stops?</Typography></DialogContent>
        <DialogActions>
          <Button onClick={() => setShowLocationDialog(false)}>No Thanks</Button>
          <Button onClick={requestLocation} variant="contained" autoFocus>Use Location</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default App;