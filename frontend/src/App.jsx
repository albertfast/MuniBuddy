// src/components/App.jsx
import React, { useState, useEffect, useCallback } from 'react';
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
import { debounce } from 'lodash';
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
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'light' ? 'dark' : 'light'));
  };

  const fetchNearbyStops = async (location) => {
    if (!location) return;
    setIsLoading(true);
    setError(null);

    try {
      const agencies = ['SF', 'SFMTA', 'muni', 'BA', 'bart'];
      const visited = new Set();
      const stopsFound = {};
      const vehicleMarkers = [];

      for (const agency of agencies) {
        const normAgency = agency.toUpperCase().startsWith("B") ? "BA" : "SF";
        try {
          const res = await fetch(`${BASE_URL}/bus/nearby-stops?lat=${location.lat}&lon=${location.lng}&radius=${radius}&agency=${agency}`);
          if (!res.ok) continue;

          const stops = await res.json();

          for (const stop of stops) {
            const stopCode = stop.stop_code || stop.stop_id;
            const stopKey = `${stopCode}-${normAgency}`;

            if (visited.has(stopKey)) continue;
            visited.add(stopKey);
            stopsFound[stop.stop_id] = stop;

            const vres = await fetch(`${BASE_URL}/bus-positions/by-stop?stopCode=${stopCode}&agency=${normAgency}`);
            if (!vres.ok) continue;

            const json = await vres.json();
            const visits = json?.ServiceDelivery?.StopMonitoringDelivery?.MonitoredStopVisit ?? [];

            for (let i = 0; i < visits.length; i++) {
              const journey = visits[i]?.MonitoredVehicleJourney;
              const loc = journey?.VehicleLocation;
              if (!loc?.Latitude || !loc?.Longitude) continue;

              vehicleMarkers.push({
                position: { lat: parseFloat(loc.Latitude), lng: parseFloat(loc.Longitude) },
                title: `${journey?.PublishedLineName || "Transit"} → ${journey?.MonitoredCall?.DestinationDisplay || "?"}`,
                stopId: `${stopCode}-${agency}-${i}`,
                icon: {
                  url: '/images/live-bus-icon.svg',
                  scaledSize: { width: 28, height: 28 }
                }
              });
            }
          }
        } catch (err) {
          console.warn(`[511 FETCH ERROR] ${agency}: ${err.message}`);
        }
      }

      setNearbyStops(stopsFound);

      const stopMarkers = Object.values(stopsFound).map((stop) => ({
        position: { lat: parseFloat(stop.stop_lat), lng: parseFloat(stop.stop_lon) },
        title: stop.stop_name,
        stopId: stop.stop_id,
        icon: { url: '/images/bus-stop-icon32.svg', scaledSize: { width: 32, height: 32 } }
      }));

      if (userLocation) {
        stopMarkers.push({
          position: userLocation,
          title: 'You',
          icon: { url: '/images/user-location-icon.svg', scaledSize: { width: 32, height: 32 } }
        });
      }

      setMarkers([...stopMarkers, ...vehicleMarkers]);
      setLiveVehicleMarkers(vehicleMarkers);

    } catch (err) {
      console.error("Master fetchNearbyStops error:", err);
      setError("Failed to load live data from 511.");
      setNearbyStops({});
    } finally {
      setIsLoading(false);
    }
  };

  const debouncedFetchNearbyStops = useCallback(debounce(fetchNearbyStops, 800), [radius]);

  const requestLocation = () => {
    setShowLocationDialog(false);
    if (navigator.geolocation) {
      setIsLoading(true);
      setError(null);
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const location = { lat: pos.coords.latitude, lng: pos.coords.longitude };
          setUserLocation(location);
          debouncedFetchNearbyStops(location);
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

  useEffect(() => {
    if (Object.keys(nearbyStops).length === 0) return;

    let cancel = false;

    const fetchAllLiveMarkers = async () => {
      const agencies = ['SF', 'SFMTA', 'muni', 'BA', 'bart'];
      let allMarkers = [];

      for (const stop of Object.values(nearbyStops)) {
        const stopCode = stop.stop_code || stop.stop_id;

        for (const agency of agencies) {
          try {
            const res = await fetch(`${BASE_URL}/bus-positions/by-stop?stopCode=${stopCode}&agency=${agency}`);
            const json = await res.json();
            const visits = json?.ServiceDelivery?.StopMonitoringDelivery?.MonitoredStopVisit ?? [];

            const markers = visits.map((visit, i) => {
              const loc = visit?.MonitoredVehicleJourney?.VehicleLocation;
              if (!loc?.Latitude || !loc?.Longitude) return null;

              return {
                position: { lat: parseFloat(loc.Latitude), lng: parseFloat(loc.Longitude) },
                title: `${visit?.MonitoredVehicleJourney?.PublishedLineName || "Transit"} → ${visit?.MonitoredVehicleJourney?.MonitoredCall?.DestinationDisplay || "?"}`,
                stopId: `${stopCode}-${agency}-${i}`,
                icon: {
                  url: '/images/live-bus-icon.svg',
                  scaledSize: { width: 28, height: 28 }
                }
              };
            }).filter(Boolean);

            allMarkers.push(...markers);
          } catch (err) {
            console.warn(`Live vehicle fetch failed for stop ${stopCode} @ ${agency}: ${err.message}`);
          }
        }
      }

      if (!cancel) setLiveVehicleMarkers(allMarkers);
    };

    fetchAllLiveMarkers();

    return () => { cancel = true; };
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
      debouncedFetchNearbyStops(coords);
      setIsLoading(false);
      return;
    }
    try {
      const data = await geocodeAddress(input);
      if (data?.lat && data?.lng) {
        const location = { lat: data.lat, lng: data.lng };
        setUserLocation(location);
        setSearchAddress(formatCoordinates(data.lat, data.lng));
        debouncedFetchNearbyStops(location);
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
      {/* UI rendering code remains unchanged */}
    </Container>
  );
};

export default App;
