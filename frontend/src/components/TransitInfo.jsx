// src/components/TransitInfo.jsx
import React, { useState, useCallback, useMemo, useEffect } from 'react';
import {
  Card, CardContent, Typography, ListItemButton, Box, Collapse, CircularProgress,
  Stack, Chip, Button, Alert, Fade, useTheme
} from '@mui/material';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import RefreshIcon from '@mui/icons-material/Refresh';
import axios from 'axios';

const SCHEDULE_CACHE = {};
const CACHE_TTL = 5 * 60 * 1000;
const API_TIMEOUT = 50000;
const API_BASE_URL = import.meta.env.VITE_API_BASE ?? 'https://munibuddy.live/api/v1';

const normalizeId = (stop) => stop?.gtfs_stop_id || stop?.stop_code || stop?.stop_id || stop?.stopId;
const getAgency = (stop) => (stop?.agency || "muni").toLowerCase();

const formatTime = (isoTime) => {
  if (!isoTime || isoTime === "Unknown") return "Unknown";
  if (/\d{1,2}:\d{2}\s[AP]M/i.test(isoTime)) return isoTime;
  try {
    const date = new Date(isoTime);
    return isNaN(date.getTime())
      ? isoTime
      : date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  } catch {
    return isoTime;
  }
};

const getStatusColor = (status = '') => {
  const s = status.toLowerCase();
  if (s.includes('late')) return 'error';
  if (s.includes('early')) return 'warning';
  return 'success';
};

const TransitInfo = ({ stops, setLiveVehicleMarkers }) => {
  const theme = useTheme();
  const [selectedStopId, setSelectedStopId] = useState(null);
  const [stopSchedule, setStopSchedule] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [intervalId, setIntervalId] = useState(null);
  const stopsArray = useMemo(() => Array.isArray(stops) ? stops : Object.values(stops), [stops]);

  const getCachedSchedule = useCallback((id) => {
    const c = SCHEDULE_CACHE[id];
    return c && (Date.now() - c.timestamp < CACHE_TTL) ? c.data : null;
  }, []);

  const setCachedSchedule = useCallback((id, data) => {
    SCHEDULE_CACHE[id] = { data, timestamp: Date.now() };
  }, []);

  const fetchSchedule = useCallback(async (id, agency = "muni") => {
    try {
      if (agency === "bart") {
        const res = await axios.get(`${API_BASE_URL}/bart-positions/by-stop`, {
          params: { stopCode: id, agency },
          timeout: API_TIMEOUT
        });
        const outbound = res.data.arrivals.map(arrival => ({
          route_number: arrival.route,
          destination: arrival.destination,
          arrival_time: arrival.expected || arrival.aimed,
          status: arrival.expected ? 'Live' : 'Scheduled',
          lat: arrival.lat,
          lon: arrival.lon,
          minutes_until: arrival.minutes_until
        }));
        return { inbound: [], outbound };
      } else {
        const res = await axios.get(`${API_BASE_URL}/stop-predictions/${id}?agency=${agency}`, {
          timeout: API_TIMEOUT
        });
        return res.data || { inbound: [], outbound: [] };
      }
    } catch (err) {
      console.error(`[fetchSchedule] Error for stop=${id}, agency=${agency}:`, err);
      throw new Error('Failed to load stop schedule. Please try again.');
    }
  }, []);

  const updateLiveVehicleMarkers = async (stopId) => {
    try {
      const res = await axios.get(`${API_BASE_URL}/bart-positions/by-stop?stopCode=${stopId}`);
      const vehicles = res.data.arrivals.filter(v => v.lat && v.lon);
      const soonVehicles = vehicles.filter(v => {
        if (v.minutes_until !== undefined) return v.minutes_until <= 5;
        return true;
      });
      const markers = soonVehicles.map(v => ({
        position: { lat: parseFloat(v.lat), lng: parseFloat(v.lon) },
        title: v.destination || v.route,
        route: v.route
      }));
      setLiveVehicleMarkers(markers);
    } catch (err) {
      console.warn("Failed to fetch live vehicle markers", err);
      setLiveVehicleMarkers([]);
    }
  };

  const handleStopClick = useCallback(async (stop) => {
    const stopId = normalizeId(stop);
    const agency = getAgency(stop);

    if (!stopId) {
      console.warn("⛔️ No valid stopId found for clicked stop:", stop);
      return;
    }

    console.log(`📍 Stop clicked → ID: ${stopId}, Agency: ${agency}`);

    if (stopId === selectedStopId) {
      console.log("🔁 Deselecting stop:", stopId);
      setSelectedStopId(null);
      setStopSchedule(null);
      setLiveVehicleMarkers([]);
      clearInterval(intervalId);
      return;
    }

    setSelectedStopId(stopId);
    setLoading(true);
    setStopSchedule(null);
    setError(null);

    const cached = getCachedSchedule(stopId);
    if (cached) {
      console.log("✅ Using cached schedule:", cached);
      setStopSchedule(cached);
      setLoading(false);
    } else {
      try {
        console.log(`🌐 Fetching new data for stop ${stopId}, agency ${agency}`);
        const schedule = await fetchSchedule(stopId, agency);
        console.log("📦 Received schedule:", schedule);
        setCachedSchedule(stopId, schedule);
        setStopSchedule(schedule);
      } catch (err) {
        console.error("❌ Fetch error:", err);
        setError(err.message);
        setStopSchedule({ inbound: [], outbound: [] });
      } finally {
        setLoading(false);
      }
    }

    clearInterval(intervalId);

    if (agency === "bart") {
      console.log("🚆 BART stop selected. Live markers enabled.");
      await updateLiveVehicleMarkers(stopId);
      const id = setInterval(() => updateLiveVehicleMarkers(stopId), 30000);
      setIntervalId(id);
    } else {
      const schedule = getCachedSchedule(stopId);
      if (schedule?.outbound?.some(r => r.vehicle && r.minutes_until <= 5)) {
        const markers = schedule.outbound
          .filter(r => r.vehicle && r.minutes_until <= 5)
          .map(r => ({
            position: { lat: r.vehicle.lat, lng: r.vehicle.lon },
            title: `${r.route_number} → ${r.destination}`,
            route: r.route_number
          }));
        console.log("🚌 MUNI vehicle markers set:", markers);
        setLiveVehicleMarkers(markers);
      } else {
        console.log("🕓 No MUNI vehicles with position arriving soon.");
        setLiveVehicleMarkers([]);
      }
    }
  }, [selectedStopId]);

  const renderRoute = (route) => {
    const routeName = route.route_number || route.route || "?";
    const arrival = route.arrival_time || route.expected || route.aimed;
    const status = route.status || (route.minutes_until !== undefined ? `${route.minutes_until} min` : '');
    return (
      <Box sx={{ borderLeft: '3px solid', borderColor: theme.palette.mode === 'dark' ? 'primary.dark' : 'primary.light', pl: 1.5, py: 0.5, mb: 1 }}>
        <Stack direction="row" justifyContent="space-between">
          <Typography variant="body2" fontWeight={500} color="primary.main">
            {routeName} → {route.destination || 'Unknown'}
          </Typography>
          {status && <Chip size="small" label={status} color={getStatusColor(status)} />}
        </Stack>
        <Typography variant="body2" color="text.secondary" mt={0.5}>
          Arrival: <b>{formatTime(arrival)}</b>
        </Typography>
      </Box>
    );
  };

  return (
    <Card elevation={2} sx={{ mt: 2 }}>
      <CardContent>
        <Typography variant="h6" fontWeight="bold" gutterBottom>
          Nearby Stops ({stopsArray.length})
        </Typography>
        {stopsArray.map((stop, i) => {
          const stopId = normalizeId(stop);
          const selected = selectedStopId === stopId;
          return (
            <Box key={`${stopId}-${i}`}>
              <ListItemButton onClick={() => handleStopClick(stop)} selected={selected}>
                <Box sx={{ flex: 1 }}>{stop.stop_name}</Box>
                {selected ? <ExpandLessIcon /> : <ExpandMoreIcon />}
              </ListItemButton>
              <Collapse in={selected} timeout="auto" unmountOnExit>
                <Box px={2} py={2}>
                  {loading ? (
                    <Box display="flex" justifyContent="center" py={2}><CircularProgress size={32} /></Box>
                  ) : error ? (
                    <Alert severity="warning" sx={{ mb: 2 }}>{error}</Alert>
                  ) : (
                    stopSchedule?.outbound?.map((r, idx) => (
                      <Fade in key={`out-${idx}`} timeout={300}><Box>{renderRoute(r)}</Box></Fade>
                    ))
                  )}
                </Box>
              </Collapse>
            </Box>
          );
        })}
      </CardContent>
    </Card>
  );
};

export default TransitInfo;
