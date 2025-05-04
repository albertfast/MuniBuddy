// frontend/src/components/TransitInfo.jsx
import React, { useState, useEffect, useCallback, useMemo } from 'react';
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
  const s = status.toLowerCase();
  if (s.includes('late')) return 'error';
  if (s.includes('early')) return 'warning';
  return 'success';
};

const renderIcon = (routeNumber) =>
  routeNumber?.toLowerCase().includes('to')
    ? <TrainIcon color="primary" fontSize="small" />
    : <DirectionsBusIcon color="secondary" fontSize="small" />;

const parseScheduleData = (visits) => {
  const grouped = { inbound: [], outbound: [] };
  for (const visit of visits) {
    const journey = visit?.MonitoredVehicleJourney;
    const call = journey?.MonitoredCall || {};
    const direction = (journey?.DirectionRef || "").toLowerCase();
    const arrivalTime = call?.ExpectedArrivalTime || call?.AimedArrivalTime;
    const arrivalDate = arrivalTime ? new Date(arrivalTime) : null;
    const now = new Date();
    const minutesUntil = arrivalDate ? Math.round((arrivalDate - now) / 60000) : null;

    const entry = {
      route_number: journey?.LineRef
        ? `${journey.LineRef} ${journey?.PublishedLineName ?? ''}`.trim()
        : journey?.PublishedLineName ?? "Unknown Line",
      destination: call?.DestinationDisplay || journey?.DestinationName,
      arrival_time: arrivalTime,
      status: minutesUntil !== null ? `${minutesUntil} min` : "Unknown",
      minutes_until: minutesUntil,
      is_realtime: true,
      vehicle: {
        lat: journey?.VehicleLocation?.Latitude || "",
        lon: journey?.VehicleLocation?.Longitude || ""
      }
    };

    console.log("🚌 Parsed entry:", entry);
    console.log("🧭 Direction:", direction);

    if (["ib", "inbound", "n"].includes(direction)) grouped.inbound.push(entry);
    else grouped.outbound.push(entry);
  }
  return grouped;
};

const TransitInfo = ({ stops, setLiveVehicleMarkers }) => {
  const [selectedStopId, setSelectedStopId] = useState(null);
  const [stopSchedule, setStopSchedule] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [nearestStops, setNearestStops] = useState({});
  const stopsArray = useMemo(() => Array.isArray(stops) ? stops : Object.values(stops), [stops]);

  useEffect(() => {
    const updateNearestStops = async () => {
      const updates = {};
      for (const dir of ['inbound', 'outbound']) {
        for (const route of stopSchedule?.[dir] || []) {
          const key = `${route.vehicle.lat},${route.vehicle.lon}`;
          if (route.vehicle?.lat && route.vehicle?.lon && !nearestStops[key]) {
            const name = await getNearestStopName(route.vehicle.lat, route.vehicle.lon);
            updates[key] = name;
          }
        }
      }
      if (Object.keys(updates).length > 0) {
        setNearestStops(prev => ({ ...prev, ...updates }));
      }
    };
    if (stopSchedule) updateNearestStops();
  }, [stopSchedule]);

  const getCachedSchedule = useCallback((stopId) => {
    const item = SCHEDULE_CACHE[stopId];
    return item && Date.now() - item.timestamp < CACHE_TTL ? item.data : null;
  }, []);

  const setCachedSchedule = useCallback((stopId, data) => {
    SCHEDULE_CACHE[stopId] = { data, timestamp: Date.now() };
  }, []);

  const getNearestStopName = async (lat, lon) => {
    try {
      const res = await axios.get(`${API_BASE_URL}/nearby-stops`, {
        params: { lat, lon, radius: 0.15, agency: 'muni' }
      });

      const stops = res.data;
      const uniqueStops = [];
      const seen = new Set();

      for (const stop of stops) {
        if (!seen.has(stop.stop_id)) {
          seen.add(stop.stop_id);
          uniqueStops.push(stop);
        }
      }

      return uniqueStops[0]?.stop_name?.trim() ?? 'Unknown stop';
    } catch (err) {
      console.warn("❌ Failed to get nearest stop name:", err.message);
      return "Unknown stop";
    }
  };

  const fetchVehiclePositions = async (stop) => {
    const stopCode = stop.stop_code || stop.stop_id;
    const agency = stop.agency?.toLowerCase();
    if (!stopCode || !agency) return;

    const isBart = agency === "bart" || agency === "ba";
    const endpoint = isBart
      ? `/bart-positions/by-stop?stopCode=${stopCode}&agency=${agency}`
      : `/bus-positions/by-stop?stopCode=${stopCode}&agency=${agency}`;

    console.log("[fetchVehiclePositions] calling:", endpoint);

    try {
      const res = await axios.get(`${API_BASE_URL}${endpoint}`);
      const visits = res.data?.ServiceDelivery?.StopMonitoringDelivery?.MonitoredStopVisit ?? [];

      const markers = visits.map((visit, i) => {
        const vehicle = visit.MonitoredVehicleJourney;
        const loc = vehicle?.VehicleLocation;
        if (!loc?.Latitude || !loc?.Longitude) return null;
        return {
          position: {
            lat: parseFloat(loc.Latitude),
            lng: parseFloat(loc.Longitude)
          },
          title: `${vehicle.PublishedLineName || "Transit"} → ${vehicle.MonitoredCall?.DestinationDisplay || "?"}`,
          stopId: `${stopCode}-${agency}-${i}`,
          icon: {
            url: '/images/live-bus-icon.svg',
            scaledSize: { width: 28, height: 28 }
          }
        };
      }).filter(Boolean);

      console.log(`[fetchVehiclePositions] received ${markers.length} markers for stop ${stopCode}`);
      setLiveVehicleMarkers(markers);
    } catch (err) {
      console.warn(`❌ Vehicle position error (${stopCode} - ${agency}):`, err.message);
    }
  };

  const handleStopClick = useCallback(async (stop) => {
    const stopId = normalizeId(stop);
    const agency = stop.agency?.toLowerCase();
    const stopCode = stop.stop_code || stop.stop_id;

    if (!stopId || !agency || !stopCode) {
      console.warn("[handleStopClick] missing data:", { stop });
      return;
    }

    if (stopId === selectedStopId) {
      setSelectedStopId(null);
      setStopSchedule(null);
      setError(null);
      return;
    }

    setSelectedStopId(stopId);
    setStopSchedule(null);
    setError(null);
    setLoading(true);

    const cached = getCachedSchedule(stopId);
    if (cached) {
      setStopSchedule(cached);
      setLoading(false);
      return;
    }

    const endpoint = agency === "bart"
      ? `/bart-positions/by-stop?stopCode=${stopCode}&agency=${agency}`
      : `/bus-positions/by-stop?stopCode=${stopCode}&agency=${agency}`;

    console.log("[handleStopClick] fetching from:", endpoint);

    try {
      const res = await axios.get(`${API_BASE_URL}${endpoint}`);
      const visits = res.data?.ServiceDelivery?.StopMonitoringDelivery?.MonitoredStopVisit ?? [];
      const parsed = parseScheduleData(visits);
      setCachedSchedule(stopId, parsed);
      setStopSchedule(parsed);
    } catch (err) {
      console.error("[handleStopClick] Error fetching schedule:", err);
      setError("Unable to load schedule.");
    } finally {
      setLoading(false);
    }

    fetchVehiclePositions(stop);
  }, [selectedStopId]);

  const handleRefreshSchedule = () => {
    if (!selectedStopId) return;
    const stop = stopsArray.find(s => normalizeId(s) === selectedStopId);
    if (stop) handleStopClick(stop);
  };

  return (
    <Card elevation={3} sx={{ mt: 2 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>Nearby Stops ({stopsArray.length})</Typography>
        <List disablePadding>
          {stopsArray.map((stop) => {
            const sid = normalizeId(stop);
            const isSelected = sid === selectedStopId;

            return (
              <React.Fragment key={sid}>
                <ListItemButton onClick={() => handleStopClick(stop)} selected={isSelected}>
                  <Box flex={1}>
                    <Stack direction="row" spacing={1} alignItems="center" mb={0.5}>
                      <LocationOnIcon color="primary" fontSize="small" />
                      <Typography fontWeight={500} noWrap>{stop.stop_name || "Unknown Stop"}</Typography>
                    </Stack>
                    <Stack direction="row" justifyContent="space-between">
                      <Typography variant="caption" color="text.secondary">Stop ID: {sid}</Typography>
                      {stop.distance_miles !== undefined && (
                        <Chip size="small" label={`${stop.distance_miles} mi`} />
                      )}
                    </Stack>
                  </Box>
                  {isSelected ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                </ListItemButton>
                <Collapse in={isSelected} timeout="auto" unmountOnExit>
                  <Box px={2} pb={2} pt={1}>
                    <Button size="small" variant="outlined" startIcon={<RefreshIcon />} onClick={handleRefreshSchedule} sx={{ mb: 1 }}>
                      Refresh
                    </Button>
                    {loading ? (
                      <Box py={3} display="flex" justifyContent="center"><CircularProgress size={28} /></Box>
                    ) : stopSchedule ? (
                      <>
                        {error && <Alert severity="warning" sx={{ mb: 2 }}>{error}</Alert>}
                        {["inbound", "outbound"].map((dir) => (
                          stopSchedule[dir]?.length > 0 && (
                            <Box key={dir} mb={2}>
                              <Typography variant="subtitle1" gutterBottom>{dir.charAt(0).toUpperCase() + dir.slice(1)}</Typography>
                              <List dense disablePadding>
                                {stopSchedule[dir].map((route, i) => (
                                  <ListItem key={`${dir}-${i}`} disablePadding>
                                    <ListItemText
                                      primary={
                                        <>
                                          {renderIcon(route.route_number)}
                                          <strong style={{ marginLeft: 6 }}>{route.route_number}</strong> → {route.destination}
                                          <Typography component="span" variant="body2" sx={{ float: "right" }} color={getStatusColor(route.status)}>
                                            {formatTime(route.arrival_time)} ({route.status})
                                          </Typography>
                                          {route.vehicle?.lat && route.vehicle?.lon && (
                                            <>
                                              <br />
                                              <Typography variant="caption" color="text.secondary">
                                                Nearest Stop: {nearestStops[`${route.vehicle.lat},${route.vehicle.lon}`] || '...'}
                                              </Typography>
                                            </>
                                          )}
                                        </>
                                      }
                                      disableTypography
                                    />
                                  </ListItem>
                                ))}
                              </List>
                            </Box>
                          )
                        ))}
                      </>
                    ) : (
                      <Typography variant="body2" color="text.secondary">No schedule available.</Typography>
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
