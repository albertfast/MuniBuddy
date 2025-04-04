import React, { useState, useCallback } from 'react';
import {
  Card, CardContent, Typography, List, ListItem, ListItemText, ListItemButton,
  Divider, Box, Collapse, CircularProgress, Stack, Chip, IconButton,
  Button, Alert
} from '@mui/material';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import RefreshIcon from '@mui/icons-material/Refresh';
import axios from 'axios';

const SCHEDULE_CACHE = {};
const CACHE_TTL = 2 * 60 * 1000;

const normalizeId = (stop) => stop.stop_id || stop.id;

const TransitInfo = ({ stops }) => {
  const [selectedStop, setSelectedStop] = useState(null);
  const [stopSchedule, setStopSchedule] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const stopsArray = Array.isArray(stops) ? stops : Object.values(stops);

  const getCachedSchedule = (stopId) => {
    const cacheItem = SCHEDULE_CACHE[stopId];
    const isValid = cacheItem && (Date.now() - cacheItem.timestamp < CACHE_TTL);
    return isValid ? cacheItem.data : null;
  };

  const setCachedSchedule = (stopId, data) => {
    SCHEDULE_CACHE[stopId] = { data, timestamp: Date.now() };
  };

  const handleStopClick = async (stop) => {
    const stopId = normalizeId(stop);

    if (normalizeId(selectedStop) === stopId) {
      setSelectedStop(null);
      setStopSchedule(null);
      return;
    }

    setSelectedStop(stop);
    setLoading(true);
    setError(null);

    const cachedData = getCachedSchedule(stopId);
    if (cachedData) {
      setStopSchedule(cachedData);
      setLoading(false);
      return;
    }

    try {
      const apiBaseUrl = import.meta.env.VITE_API_BASE ?? 'https://munibuddy.live/api/v1';
      const response = await axios.get(`${apiBaseUrl}/stop-schedule/${stopId}`, { timeout: 10000 });

      if (response.data) {
        setCachedSchedule(stopId, response.data);
        setStopSchedule(response.data);
      }
    } catch (err) {
      setError('Failed to load stop schedule. Please check your internet connection.');
      setStopSchedule({ inbound: [], outbound: [] });
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshSchedule = useCallback(async () => {
    if (!selectedStop) return;

    const stopId = normalizeId(selectedStop);
    setLoading(true);
    setError(null);

    try {
      const apiBaseUrl = import.meta.env.VITE_API_BASE ?? 'https://munibuddy.live/api/v1';
  const response = await axios.get(`${apiBaseUrl}/stop-schedule/${stopId}`, {
    timeout: 10000,
    params: { _t: Date.now() }
  });

  setCachedSchedule(stopId, response.data);
  setStopSchedule(response.data);
    } catch (err) {
      setError('Failed to refresh schedule. Please check your connection.');
    } finally {
      setLoading(false);
    }
  }, [selectedStop]);

  const formatTime = (isoTime) => {
    if (!isoTime || isoTime === "Unknown") return "Unknown";
    if (/\d{1,2}:\d{2}\s[AP]M/.test(isoTime)) return isoTime;

    try {
      const date = new Date(isoTime);
      return isNaN(date.getTime())
      ? isoTime
      : date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    } catch {
      return isoTime;
    }
  };

  const getStatusColor = (status) => {
    if (status.includes('late')) return 'error';
    if (status === 'Early') return 'warning';
    return 'success';
  };

  const renderStopInfo = (stop) => (
    <>
    <Stack direction="row" alignItems="center" spacing={1}>
    <LocationOnIcon color="primary" />
    <Typography variant="body1" fontWeight={500}>
    {stop.stop_name}
    </Typography>
    </Stack>
    <Stack direction="row" justifyContent="space-between" mt={0.5}>
    <Box display="flex" alignItems="center">
    <DirectionsBusIcon fontSize="small" sx={{ mr: 0.5 }} />
    <Typography variant="body2" color="text.secondary">
    Stop ID: {normalizeId(stop)}
    </Typography>
    </Box>
    <Chip
    size="small"
    label={`${stop.distance_miles} miles`}
    sx={{ height: '20px', fontSize: '0.7rem', bgcolor: 'rgba(25, 118, 210, 0.08)' }}
    />
    </Stack>
    {stop.routes?.length > 0 && (
      <Typography variant="body2" color="text.secondary" fontSize="0.75rem" mt={0.5}>
      Routes: {stop.routes.map(r => r.route_number).join(', ')}
      </Typography>
    )}
    </>
  );

  const renderRouteInfo = (route) => (
    <Box sx={{ borderLeft: '3px solid #1976d2', pl: 1, py: 0.5, mb: 1 }}>
    <Stack direction="row" justifyContent="space-between">
    <Typography variant="body1" fontWeight="medium" color="primary">
    {route.route_number} →{' '}
    <Box component="span" fontWeight={route.destination?.toLowerCase().includes('transit center') ? 'bold' : 'medium'} color={route.destination?.toLowerCase().includes('transit center') ? 'error.main' : 'inherit'}>
    {route.destination}
    </Box>
    </Typography>
    <Chip size="small" label={route.status} color={getStatusColor(route.status)} />
    </Stack>
    <Typography variant="body2" color="text.secondary" mt={0.5}>
    Arrival: <b>{formatTime(route.arrival_time)}</b> {route.stops_away && ` • ${route.stops_away} stops away`}
    </Typography>
    </Box>
  );

  return (
    <Card elevation={2} sx={{ borderRadius: 2 }}>
    <CardContent sx={{ pb: 1 }}>
    <Typography variant="h6" fontWeight="bold" color="primary" gutterBottom>
    Nearby Stops ({stopsArray.length})
    </Typography>
    <List>
    {stopsArray.map((stop, index) => {
      const stopId = normalizeId(stop);
      const isSelected = selectedStop && normalizeId(selectedStop) === stopId;

      return (
        <React.Fragment key={stopId}>
        <ListItemButton
        onClick={() => handleStopClick(stop)}
        selected={isSelected}
        sx={{
          borderRadius: 1,
          mb: 0.5,
          '&.Mui-selected': { backgroundColor: 'rgba(25, 118, 210, 0.08)' }
        }}
        >
        <ListItemText primary={renderStopInfo(stop)} />
        <IconButton onClick={(e) => { e.stopPropagation(); handleStopClick(stop); }} size="small">
        {isSelected ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        </IconButton>
        </ListItemButton>

        <Collapse in={isSelected}>
        <Box px={2} pb={2}>
        {loading && isSelected ? (
          <Box display="flex" justifyContent="center" p={2}>
          <CircularProgress size={28} />
          </Box>
        ) : stopSchedule && isSelected ? (
          <>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

          {stopSchedule.inbound?.length > 0 && (
            <Box mb={2}>
            <Stack direction="row" spacing={1} mb={1}>
            <ArrowDownwardIcon color="primary" fontSize="small" />
            <Typography variant="subtitle2" color="primary" fontWeight="bold">
            Inbound Routes
            </Typography>
            </Stack>
            <List dense>
            {stopSchedule.inbound.map((route, i) => (
              <ListItem key={i} sx={{ px: 0 }}>
              <ListItemText primary={renderRouteInfo(route)} disableTypography />
              </ListItem>
            ))}
            </List>
            </Box>
          )}

          {stopSchedule.outbound?.length > 0 && (
            <Box>
            <Stack direction="row" spacing={1} mb={1}>
            <ArrowUpwardIcon color="primary" fontSize="small" />
            <Typography variant="subtitle2" color="primary" fontWeight="bold">
            Outbound Routes
            </Typography>
            </Stack>
            <List dense>
            {stopSchedule.outbound.map((route, i) => (
              <ListItem key={i} sx={{ px: 0 }}>
              <ListItemText primary={renderRouteInfo(route)} disableTypography />
              </ListItem>
            ))}
            </List>
            </Box>
          )}

          {!stopSchedule.inbound?.length && !stopSchedule.outbound?.length && (
            <Typography textAlign="center" color="text.secondary" py={2}>
            No scheduled routes at this time.
            </Typography>
          )}

          <Box display="flex" justifyContent="center" mt={2}>
          <Button
          startIcon={<RefreshIcon />}
          onClick={handleRefreshSchedule}
          disabled={loading}
          variant="outlined"
          size="small"
          sx={{ borderRadius: '20px', textTransform: 'none', px: 2 }}
          >
          Refresh
          </Button>
          </Box>
          </>
        ) : null}
        </Box>
        </Collapse>

        {index < stopsArray.length - 1 && <Divider sx={{ my: 0.5 }} />}
        </React.Fragment>
      );
    })}
    </List>
    </CardContent>
    </Card>
  );
};

export default TransitInfo;
