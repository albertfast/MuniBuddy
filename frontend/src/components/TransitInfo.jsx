// src/components/TransitInfo.jsx - hybrid optimized version
import React, { useState, useCallback, useMemo } from 'react';
import {
  Card, CardContent, Typography, ListItemButton, Box, Collapse, CircularProgress,
  Stack, Chip, Button, Alert, Fade
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

const normalizeId = (stop) => stop?.gtfs_stop_id || stop?.stop_code || stop?.stop_id;

const formatTime = (isoTime) => {
  if (!isoTime || isoTime === 'Unknown') return 'Unknown';
  try {
    const date = new Date(isoTime);
    return date.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    });
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

const TransitInfo = ({ stops }) => {
  const [selectedStopId, setSelectedStopId] = useState(null);
  const [stopSchedule, setStopSchedule] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const stopsArray = useMemo(() => Array.isArray(stops) ? stops : Object.values(stops), [stops]);

  const getCachedSchedule = useCallback((id) => {
    const c = SCHEDULE_CACHE[id];
    return c && (Date.now() - c.timestamp < CACHE_TTL) ? c.data : null;
  }, []);

  const setCachedSchedule = useCallback((id, data) => {
    SCHEDULE_CACHE[id] = { data, timestamp: Date.now() };
  }, []);

  const fetchSchedule = useCallback(async (id) => {
    try {
      const res = await axios.get(`${API_BASE_URL}/stop-predictions/${id}`, { timeout: API_TIMEOUT });
      return res.data || { inbound: [], outbound: [] };
    } catch {
      throw new Error('Failed to load stop schedule. Please try again.');
    }
  }, []);

  const handleStopClick = useCallback(async (stop) => {
    const stopId = normalizeId(stop);
    if (!stopId) return;

    if (stopId === selectedStopId) {
      setSelectedStopId(null);
      setStopSchedule(null);
      return;
    }

    setSelectedStopId(stopId);
    setLoading(true);
    setStopSchedule(null);
    setError(null);

    const cached = getCachedSchedule(stopId);
    if (cached) {
      setStopSchedule(cached);
      setLoading(false);
      return;
    }

    try {
      const schedule = await fetchSchedule(stopId);
      setCachedSchedule(stopId, schedule);
      setStopSchedule(schedule);
    } catch (err) {
      setError(err.message);
      setStopSchedule({ inbound: [], outbound: [] });
    } finally {
      setLoading(false);
    }
  }, [selectedStopId, fetchSchedule, getCachedSchedule, setCachedSchedule]);

  const handleRefresh = async () => {
    if (!selectedStopId) return;
    setLoading(true);
    setError(null);
    try {
      const schedule = await fetchSchedule(selectedStopId);
      setCachedSchedule(selectedStopId, schedule);
      setStopSchedule(schedule);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const renderStop = useCallback((stop) => (
    <>
      <Stack direction="row" alignItems="center" spacing={1} mb={0.5}>
        <LocationOnIcon color="primary" fontSize="small" />
        <Typography variant="body1" fontWeight={500} noWrap>
          {stop.stop_name || 'Unknown'}
        </Typography>
      </Stack>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Box display="flex" alignItems="center">
          <DirectionsBusIcon fontSize="small" sx={{ mr: 0.5 }} />
          <Typography variant="caption">Stop ID: {normalizeId(stop)}</Typography>
        </Box>
        {stop.distance_miles !== undefined && (
          <Chip size="small" label={`${stop.distance_miles} mi`} />
        )}
      </Stack>
    </>
  ), []);

  const renderRoute = useCallback((route) => (
    <Box className="transit-info-panel" sx={{ borderLeft: '3px solid', borderColor: 'primary.light', pl: 1.5, py: 0.5, mb: 1 }}>
      <Stack direction="row" justifyContent="space-between">
        <Typography variant="body2" fontWeight={500} color="primary.main">
          {route.route_number || 'Route ?'} → {route.destination || 'Unknown'}
        </Typography>
        {route.status && <Chip size="small" label={route.status} color={getStatusColor(route.status)} />}
      </Stack>
      <Typography variant="body2">
        Arrival: {formatTime(route.arrival_time)}
      </Typography>
    </Box>
  ), []);

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
                <Box sx={{ flex: 1 }}>{renderStop(stop)}</Box>
                {selected ? <ExpandLessIcon /> : <ExpandMoreIcon />}
              </ListItemButton>
              <Collapse in={selected} timeout="auto" unmountOnExit>
                <Fade in={Boolean(stopSchedule)} timeout={300}>
                  <Box px={2} py={2}>
                    {loading ? (
                      <Box display="flex" justifyContent="center" py={2}><CircularProgress size={32} /></Box>
                    ) : (
                      <>
                        {error && <Alert severity="warning" sx={{ mb: 2 }}>{error}</Alert>}
                        {stopSchedule?.inbound?.length > 0 && (
                          <Box mb={2}>
                            <Typography variant="subtitle1">Inbound</Typography>
                            {stopSchedule.inbound.map((r, idx) => (
                              <Fade in key={`in-${idx}`} timeout={300}><Box>{renderRoute(r)}</Box></Fade>
                            ))}
                          </Box>
                        )}
                        {stopSchedule?.outbound?.length > 0 && (
                          <Box>
                            <Typography variant="subtitle1">Outbound</Typography>
                            {stopSchedule.outbound.map((r, idx) => (
                              <Fade in key={`out-${idx}`} timeout={300}><Box>{renderRoute(r)}</Box></Fade>
                            ))}
                          </Box>
                        )}
                        {stopSchedule?.inbound?.length === 0 && stopSchedule?.outbound?.length === 0 && (
                          <Typography variant="body2" color="text.secondary">
                            No upcoming buses.
                          </Typography>
                        )}
                        <Box display="flex" justifyContent="center" mt={2}>
                          <Button size="small" startIcon={<RefreshIcon />} onClick={handleRefresh} disabled={loading}>
                            {loading ? 'Refreshing...' : 'Refresh'}
                          </Button>
                        </Box>
                      </>
                    )}
                  </Box>
                </Fade>
              </Collapse>
            </Box>
          );
        })}
      </CardContent>
    </Card>
  );
};

export default TransitInfo;
