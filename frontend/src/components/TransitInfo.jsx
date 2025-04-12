import React, { useState, useCallback, useMemo } from 'react';
import {
  Card, CardContent, Typography, List, ListItem, ListItemText, ListItemButton,
  Divider, Box, Collapse, CircularProgress, Stack, Chip, IconButton,
  Button, Alert
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

// ✅ GTFS ID first for API calls, then fallback to display stop_id
const normalizeId = (stop) => stop?.gtfs_stop_id || stop?.stop_id;

const formatTime = (isoTime) => {
  if (!isoTime || isoTime === "Unknown") return "Unknown";
  if (/\d{1,2}:\d{2}\s[AP]M/i.test(isoTime)) {
    const [time, period] = isoTime.split(' ');
    const [hours, minutes] = time.split(':');
    return `${hours.padStart(2, '0')}:${minutes} ${period}`;
  }
  try {
    const date = new Date(isoTime);
    return isNaN(date.getTime())
      ? isoTime
      : date.toLocaleTimeString('en-US', {
          hour: '2-digit',
          minute: '2-digit',
          hour12: true,
          timeZone: 'America/Los_Angeles'
        });
  } catch {
    return isoTime;
  }
};

const getStatusColor = (status = '') => {
  const lowerStatus = status.toLowerCase();
  if (lowerStatus.includes('late')) return 'error';
  if (lowerStatus.includes('early')) return 'warning';
  return 'success';
};

const TransitInfo = ({ stops }) => {
  const [selectedStopId, setSelectedStopId] = useState(null);
  const [stopSchedule, setStopSchedule] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const stopsArray = useMemo(() => Array.isArray(stops) ? stops : Object.values(stops), [stops]);

  const getCachedSchedule = useCallback((stopId) => {
    const cacheItem = SCHEDULE_CACHE[stopId];
    return cacheItem && (Date.now() - cacheItem.timestamp < CACHE_TTL)
      ? cacheItem.data
      : null;
  }, []);

  const setCachedSchedule = useCallback((stopId, data) => {
    SCHEDULE_CACHE[stopId] = { data, timestamp: Date.now() };
  }, []);

  const handleStopClick = useCallback(async (stopToSelect) => {
    const stopIdToSelect = stopToSelect.gtfs_stop_id;
    if (selectedStopId === stopIdToSelect) {
      setSelectedStopId(null);
      setStopSchedule(null);
      setError(null);
      return;
    }

    setSelectedStopId(stopIdToSelect);
    setLoading(true);
    setError(null);
    setStopSchedule(null);

    const cachedData = getCachedSchedule(stopIdToSelect);
    if (cachedData) {
      setStopSchedule(cachedData);
      setLoading(false);
      return;
    }

    try {
      const response = await axios.get(`${API_BASE_URL}/stop-predictions/${stopIdToSelect}`, {
        timeout: API_TIMEOUT
      });
      if (response.data) {
        setCachedSchedule(stopIdToSelect, response.data);
        setStopSchedule(response.data);
      } else {
        setStopSchedule({ inbound: [], outbound: [] });
      }
    } catch (err) {
      setError('Failed to load stop schedule. Please check network or try again.');
      setStopSchedule({ inbound: [], outbound: [] });
    } finally {
      setLoading(false);
    }
  }, [selectedStopId, getCachedSchedule, setCachedSchedule]);

  const handleRefreshSchedule = useCallback(async () => {
    if (!selectedStopId) return;
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get(`${API_BASE_URL}/stop-predictions/${selectedStopId}`, {
        timeout: API_TIMEOUT,
        params: { _t: Date.now() }
      });
      setCachedSchedule(selectedStopId, response.data);
      setStopSchedule(response.data);
    } catch (err) {
      setError('Failed to refresh schedule. Please check connection.');
    } finally {
      setLoading(false);
    }
  }, [selectedStopId, setCachedSchedule]);

  const renderStopInfo = useCallback((stop) => (
    <>
      <Stack direction="row" alignItems="center" spacing={1} mb={0.5}>
        <LocationOnIcon color="primary" fontSize="small" />
        <Typography variant="body1" fontWeight={500} noWrap>
          {stop.stop_name || 'Unknown Stop Name'}
        </Typography>
      </Stack>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Box display="flex" alignItems="center">
          <DirectionsBusIcon fontSize="small" sx={{ mr: 0.5, color: 'text.secondary' }} />
          <Typography variant="caption" color="text.secondary">
            Stop ID: {stop.stop_id || stop.gtfs_stop_id || 'Unknown'}
          </Typography>
        </Box>
        {stop.distance_miles !== undefined && (
          <Chip size="small" label={`${stop.distance_miles} miles`} />
        )}
      </Stack>
    </>
  ), []);  

  const renderRouteInfo = useCallback((route) => (
    <Box sx={{ borderLeft: '3px solid', borderColor: 'primary.light', pl: 1.5, py: 0.5, mb: 1 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
        <Typography variant="body2" fontWeight="medium" color="primary.main">
          {route.route_number || 'Route ?'} → <Box component="span">{route.destination || 'Unknown Destination'}</Box>
        </Typography>
        {route.status && (
            <Chip size="small" label={route.status} color={getStatusColor(route.status)} />
        )}
      </Stack>
      <Typography variant="body2" color="text.secondary" mt={0.5}>
        Arrival: <b>{formatTime(route.arrival_time)}</b>
      </Typography>
    </Box>
  ), []);

  return (
    <Card elevation={2}>
      <CardContent>
        <Typography variant="h6" component="h2" fontWeight="bold" color="primary.main" gutterBottom>
          Nearby Stops ({stopsArray.length})
        </Typography>
        <List>
          {stopsArray.map((stop, index) => {
            const currentStopId = stop.gtfs_stop_id;
            const isSelected = selectedStopId === currentStopId;
            return (
              <React.Fragment key={`${stop.stop_id}-${index}`}>
                <ListItemButton onClick={() => handleStopClick(stop)} selected={isSelected}>
                  <Box sx={{ flex: 1 }}>{renderStopInfo(stop)}</Box>
                  <IconButton onClick={(e) => { e.stopPropagation(); handleStopClick(stop); }} size="small">
                    {isSelected ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                  </IconButton>
                </ListItemButton>
                <Collapse in={isSelected} timeout="auto" unmountOnExit>
                  <Box px={2} pb={2} pt={1}>
                    {loading ? (
                      <Box display="flex" justifyContent="center" py={3}>
                        <CircularProgress size={32} />
                      </Box>
                    ) : stopSchedule ? (
                      <>
                        {error && <Alert severity="warning" sx={{ mb: 2 }}>{error}</Alert>}
                        {stopSchedule.inbound?.length > 0 && (
                          <Box mb={2}>
                            <Typography variant="subtitle1">Inbound</Typography>
                            <List dense disablePadding>
                              {stopSchedule.inbound.map((route, i) => (
                                <ListItem key={`in-${i}`} disablePadding>
                                  <ListItemText primary={renderRouteInfo(route)} disableTypography />
                                </ListItem>
                              ))}
                            </List>
                          </Box>
                        )}
                        {stopSchedule.outbound?.length > 0 && (
                          <Box>
                            <Typography variant="subtitle1">Outbound</Typography>
                            <List dense disablePadding>
                              {stopSchedule.outbound.map((route, i) => (
                                <ListItem key={`out-${i}`} disablePadding>
                                  <ListItemText primary={renderRouteInfo(route)} disableTypography />
                                </ListItem>
                              ))}
                            </List>
                          </Box>
                        )}
                        {!stopSchedule.inbound?.length && !stopSchedule.outbound?.length && !error && (
                          <Typography textAlign="center" color="text.secondary" py={2}>
                            No scheduled routes found at this time.
                          </Typography>
                        )}
                        <Box display="flex" justifyContent="center" mt={3}>
                          <Button startIcon={<RefreshIcon />} onClick={handleRefreshSchedule} disabled={loading}>
                            {loading ? 'Refreshing...' : 'Refresh'}
                          </Button>
                        </Box>
                      </>
                    ) : null}
                  </Box>
                </Collapse>
              </React.Fragment>
            );
          })}
        </List>
      </CardContent>
    </Card>
  );
};

export default TransitInfo;
