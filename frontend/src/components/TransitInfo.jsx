import React, { useState, useCallback, useMemo } from 'react';
import {
  Card, CardContent, Typography, List, ListItem, ListItemText, ListItemButton,
  Box, Collapse, CircularProgress, Stack, Chip, Button, Alert
} from '@mui/material';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import TrainIcon from '@mui/icons-material/Train';
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
  if (!isoTime || isoTime === "Unknown") return "Unknown";
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

const renderIcon = (routeNumber) => {
  if (routeNumber?.toLowerCase().includes('to')) {
    return <TrainIcon color="primary" fontSize="small" />;
  }
  return <DirectionsBusIcon color="secondary" fontSize="small" />;
};

const TransitInfo = ({ stops, setLiveVehicleMarkers }) => {
  const [selectedStopId, setSelectedStopId] = useState(null);
  const [stopSchedule, setStopSchedule] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const stopsArray = useMemo(() => Array.isArray(stops) ? stops : Object.values(stops), [stops]);

  const fetchVehiclePositions = async (stop) => {
    const stopCode = stop.stop_code || stop.stop_id;
    const agency = stop.agency?.toLowerCase() || "sf";
  
    const agenciesToTry = agency === "bart" || agency === "ba"
      ? ["BA", "bart"]
      : ["SF", "SFMTA", "muni"];
  
    const allMarkers = [];
  
    for (const ag of agenciesToTry) {
      try {
        const res = await axios.get(`${API_BASE_URL}/bus/nearby-stops`, {
          params: { stopCode, agency: ag }
        });
  
        const visits = res.data?.ServiceDelivery?.StopMonitoringDelivery?.MonitoredStopVisit ?? [];
  
        const markers = visits.map((visit, i) => {
          const vehicle = visit.MonitoredVehicleJourney;
          const location = vehicle?.VehicleLocation;
          return {
            position: {
              lat: parseFloat(location?.Latitude),
              lng: parseFloat(location?.Longitude)
            },
            title: `${vehicle?.PublishedLineName || vehicle?.LineRef || 'Bus'} → ${vehicle?.MonitoredCall?.DestinationDisplay}`,
            stopId: `${stopCode}-${ag}-${i}`,
            icon: {
              url: '/images/live-bus-icon.svg',
              scaledSize: { width: 28, height: 28 }
            }
          };
        }).filter(m => m.position.lat && m.position.lng);
  
        allMarkers.push(...markers);
  
      } catch (err) {
        console.warn(`Live fetch failed for agency ${ag}:`, err.message);
      }
    }
  
    console.log("All live vehicle markers:", allMarkers);
    setLiveVehicleMarkers(allMarkers);
  };
  
  const getCachedSchedule = useCallback((stopId) => {
    const cacheItem = SCHEDULE_CACHE[stopId];
    return cacheItem && (Date.now() - cacheItem.timestamp < CACHE_TTL)
      ? cacheItem.data
      : null;
  }, []);

  const setCachedSchedule = useCallback((stopId, data) => {
    SCHEDULE_CACHE[stopId] = { data, timestamp: Date.now() };
  }, []);

  const normalizeResponse = (raw) => {
    const realtime = raw?.realtime || raw;
    return {
      inbound: realtime.inbound ?? [],
      outbound: realtime.outbound ?? []
    };
  };

  const handleStopClick = useCallback(async (stopToSelect) => {
    const stopIdToSelect = normalizeId(stopToSelect);
    const agency = stopToSelect.agency?.toLowerCase();
  
    if (!stopIdToSelect) return;
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
      // 🔍 Step 1: Prediction fetch (schedule or realtime fallback handled in backend)
      const predictionRes = await axios.get(`${API_BASE_URL}/stop-predictions/${stopIdToSelect}`, {
        timeout: API_TIMEOUT
      });
  
      let data = normalizeResponse(predictionRes.data);
      await fetchVehiclePositions(stopToSelect);
  
      // 🚍 Step 2: Enrich with live vehicle data (both BART and MUNI)
      const agenciesToTry = agency === "bart" ? ["BA", "bart"] : ["SF", "SFMTA", "muni"];
      let allVehicleMarkers = [];
  
      for (const ag of agenciesToTry) {
        try {
          const vehicleRes = await axios.get(`${API_BASE_URL}/bus-positions/by-stop`, {
            params: { stopCode: stopIdToSelect, agency: ag }
          });
  
          const visits = vehicleRes?.data?.ServiceDelivery?.StopMonitoringDelivery?.MonitoredStopVisit ?? [];
  
          visits.forEach((visit, index) => {
            const journey = visit.MonitoredVehicleJourney || {};
            const vehicleLoc = journey.VehicleLocation || {};
            const route = journey.PublishedLineName || journey.LineRef;
            const direction = (journey.DirectionRef || "").toLowerCase();
            const aimedTime = journey.MonitoredCall?.AimedArrivalTime || "";
            const realtimeTarget = direction.includes("i") || direction === "1" ? data.inbound : data.outbound;
  
            // Match prediction with 511 live data
            const match = realtimeTarget.find((r) =>
              r.route_number?.includes(route) && r.arrival_time?.includes(aimedTime)
            );
  
            if (match && vehicleLoc.Latitude && vehicleLoc.Longitude) {
              match.vehicle = {
                lat: vehicleLoc.Latitude,
                lon: vehicleLoc.Longitude
              };
            }
  
            // Collect marker if position available
            if (vehicleLoc.Latitude && vehicleLoc.Longitude) {
              allVehicleMarkers.push({
                position: {
                  lat: parseFloat(vehicleLoc.Latitude),
                  lng: parseFloat(vehicleLoc.Longitude)
                },
                title: `${route} → ${journey.MonitoredCall?.DestinationDisplay || "?"}`,
                stopId: `${stopIdToSelect}-${ag}-${index}`,
                icon: {
                  url: '/images/live-bus-icon.svg',
                  scaledSize: { width: 28, height: 28 }
                }
              });
            }
          });
        } catch (err) {
          console.warn(`511 API error for ${ag}:`, err.message);
        }
      }
  
      setLiveVehicleMarkers(allVehicleMarkers); // 🔴 Update map with live buses/trains
      setCachedSchedule(stopIdToSelect, data);
      setStopSchedule(data);
    } catch (err) {
      console.error("Error fetching stop data:", err);
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
      const data = normalizeResponse(response.data);
      setCachedSchedule(selectedStopId, data);
      setStopSchedule(data);
    } catch (err) {
      setError('Failed to refresh schedule. Please check connection.');
    } finally {
      setLoading(false);
    }
  }, [selectedStopId, setCachedSchedule]);

  const renderRouteInfo = (route) => (
    <Box sx={{ borderLeft: '3px solid', borderColor: 'primary.light', pl: 1.5, py: 0.5, mb: 1 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
        <Typography variant="body2" fontWeight="medium" color="primary.main">
          {renderIcon(route.route_number)} {route.route_number || 'Route ?'} → {route.destination || 'Unknown'}
        </Typography>
        {route.status && (
          <Chip size="small" label={route.status} color={getStatusColor(route.status)} />
        )}
      </Stack>
      <Typography variant="body2" color="text.secondary">
        Arrival: <b>{formatTime(route.arrival_time)}</b>
      </Typography>
      {route.vehicle?.lat && route.vehicle?.lon ? (
        <Typography variant="caption" color="text.secondary">
          Vehicle Location: ({route.vehicle.lat}, {route.vehicle.lon})
        </Typography>
      ) : (
        <Typography variant="caption" color="text.disabled">
          Vehicle location unavailable
        </Typography>
      )}
    </Box>
  );

  const renderStopInfo = (stop) => (
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
            Stop ID: {normalizeId(stop) || 'Unknown'}
          </Typography>
        </Box>
        {stop.distance_miles !== undefined && (
          <Chip size="small" label={`${stop.distance_miles} miles`} />
        )}
      </Stack>
    </>
  );

  return (
    <Card elevation={2}>
      <CardContent>
        <Typography variant="h6" component="h2" fontWeight="bold" color="primary.main" gutterBottom>
          Nearby Stops ({stopsArray.length})
        </Typography>
        <List>
          {stopsArray.map((stop, index) => {
            const currentStopId = normalizeId(stop);
            if (!currentStopId) return null;
            const isSelected = selectedStopId === currentStopId;

            return (
              <React.Fragment key={`${stop.stop_id}-${index}`}>
                <ListItemButton onClick={() => handleStopClick(stop)} selected={isSelected}>
                  <Box sx={{ flex: 1 }}>{renderStopInfo(stop)}</Box>
                  {isSelected ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                </ListItemButton>

                <Collapse in={isSelected} timeout="auto" unmountOnExit>
                  <Box px={2} pb={2} pt={1}>
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={<RefreshIcon />}
                      onClick={handleRefreshSchedule}
                      sx={{ mb: 1 }}
                    >
                      Refresh
                    </Button>
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
                        {stopSchedule.inbound?.length === 0 && stopSchedule.outbound?.length === 0 && (
                          <Typography variant="body2" color="text.secondary">
                            No upcoming transit found.
                          </Typography>
                        )}
                      </>
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        No schedule available.
                      </Typography>
                    )}
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