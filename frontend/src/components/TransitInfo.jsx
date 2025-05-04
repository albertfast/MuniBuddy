// frontend/src/components/TransitInfo.jsx
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

axios.interceptors.request.use((config) => {
    console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url}`, config.params || {});
    return config;
  });
  
  axios.interceptors.response.use((res) => {
    console.log(`[API Response] ${res.config.url}`, res.status, res.data);
    return res;
  }, (error) => {
    console.error(`[API Error] ${error.config?.url}`, error.message);
    return Promise.reject(error);
  });

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
    const s = status.toLowerCase();
    if (s.includes('late')) return 'error';
    if (s.includes('early')) return 'warning';
    return 'success';
};

const renderIcon = (routeNumber) =>
routeNumber?.toLowerCase().includes('to')
? <TrainIcon color="primary" fontSize="small" />
: <DirectionsBusIcon color="secondary" fontSize="small" />;

const getNearestStopName = async (lat, lon) => {
    try {
        const res = await axios.get(`${API_BASE_URL}/nearby-stops`, {
            params: { lat, lon, radius: 0.15, agency: 'muni' },
        });
        const stops = res.data || [];
        const seen = new Set();
        const unique = stops.filter(s => {
            if (seen.has(s.stop_id)) return false;
            seen.add(s.stop_id);
            return true;
        });
        return unique[0]?.stop_name?.trim() || 'Unknown stop';
    } catch (err) {
        console.warn('[nearestStopName] Error:', err.message);
        return 'Unknown stop';
    }
};

const normalizeSiriData = async (visits = []) => {
    const grouped = { inbound: [], outbound: [] };

    for (const visit of visits) {
        const journey = visit?.MonitoredVehicleJourney;
        const call = journey?.MonitoredCall || {};
        const direction = (journey?.DirectionRef || "").toLowerCase();

        const arrivalTime = call?.ExpectedArrivalTime || call?.AimedArrivalTime;
        const arrivalDate = arrivalTime ? new Date(arrivalTime) : null;
        const now = new Date();
        const minutesUntil = arrivalDate ? Math.round((arrivalDate - now) / 60000) : null;

        const lat = journey?.VehicleLocation?.Latitude || "";
        const lon = journey?.VehicleLocation?.Longitude || "";

        const nearestStop = (lat && lon) ? await getNearestStopName(lat, lon) : "";

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
                lat,
                lon,
                nearest_stop: nearestStop
            }
        };

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
    const stopsArray = useMemo(() => Array.isArray(stops) ? stops : Object.values(stops), [stops]);

    const getCachedSchedule = useCallback((stopId) => {
        const item = SCHEDULE_CACHE[stopId];
        return item && Date.now() - item.timestamp < CACHE_TTL ? item.data : null;
    }, []);

    const setCachedSchedule = useCallback((stopId, data) => {
        SCHEDULE_CACHE[stopId] = { data, timestamp: Date.now() };
    }, []);

    const fetchVehiclePositions = async (stop) => {
        console.log('[fetchVehiclePositions] Fetching for:', stop);
        const stopCode = stop.stop_code
        const agency = stop.agency?.toLowerCase() || "sf";
        const isBart = agency === "bart" || agency === "ba";
        const endpoint = isBart
        ? `/bart-positions/by-stop?stopCode=${stopCode}&agency=${agency}`
        : `/bus-positions/by-stop?stopCode=${stopCode}&agency=${agency}`;

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

            setLiveVehicleMarkers(markers);
        } catch (err) {
            console.warn(`Failed to fetch vehicle positions for ${stopCode} (${agency}): ${err.message}`);
        }
        console.error('[API Error]', err);
    };

    const handleStopClick = useCallback(async (stop) => {
        console.log('[handleStopClick] Stop clicked:', stop);
        let stopId = normalizeId(stop);
        const agency = stop.agency?.toLowerCase();

        if (agency === 'bart' && stopId.includes('_')) {
            stopId = stopId.split('_')[0];
        }
        if (agency === 'bart' && stopId.startsWith('place_')) {
            stopId = stopId.replace('place_', '');
        }

        if (!stopId) return;
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

        try {
            const predictionURL = agency === "bart"
            ? `/bart-positions/by-stop?stopCode=${stopId}&agency=${agency}`
            : `/bus-positions/by-stop?stopCode=${stopId}&agency=${agency}`;
            const res = await axios.get(`${API_BASE_URL}${predictionURL}`, { timeout: API_TIMEOUT });
            console.log('[API Request]', `${API_BASE_URL}${predictionURL}`);
            console.log('[API Response]', res.data);
            const data = res.data?.realtime || res.data;
            const visits = data?.ServiceDelivery?.StopMonitoringDelivery?.MonitoredStopVisit;
            const schedule = Array.isArray(visits) ? await normalizeSiriData(visits) : data;

            await fetchVehiclePositions({ stop_code: stopId, agency });
            setCachedSchedule(stopId, schedule);
            setStopSchedule(schedule);
        } catch (err) {
            setError('Failed to fetch predictions. Try again.');
            setStopSchedule({ inbound: [], outbound: [] });
        } finally {
            setLoading(false);
        }
    }, [selectedStopId, getCachedSchedule, setCachedSchedule]);

    const handleRefreshSchedule = useCallback(async () => {
        const stop = stopsArray.find(s => normalizeId(s) === selectedStopId);
        const agency = stop?.agency ?? 'muni';
        const isBart = agency.toLowerCase() === 'bart' || agency.toLowerCase() === 'ba';

        const refreshURL = isBart
        ? `/bart-positions/by-stop?stopCode=${selectedStopId}&agency=${agency}`
        : `/bus-positions/by-stop?stopCode=${selectedStopId}&agency=${agency}`;

        if (!selectedStopId) return;
        setLoading(true);
        setError(null);
        try {
            const res = await axios.get(`${API_BASE_URL}${refreshURL}`, {
                timeout: API_TIMEOUT,
                params: { _t: Date.now() }
            });
            const data = res.data?.realtime || res.data;
            const visits = data?.ServiceDelivery?.StopMonitoringDelivery?.MonitoredStopVisit;
            const schedule = Array.isArray(visits) ? await normalizeSiriData(visits) : data;

            setCachedSchedule(selectedStopId, schedule);
            setStopSchedule(schedule);
        } catch {
            setError('Failed to refresh schedule.');
        } finally {
            setLoading(false);
        }
    }, [selectedStopId, stopsArray, setCachedSchedule]);

    const renderRouteInfo = (route) => (
        <Box sx={{ borderLeft: '3px solid', borderColor: 'primary.light', pl: 1.5, py: 0.5, mb: 1 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
        <Typography variant="body2" fontWeight="medium" color="primary.main">
        {renderIcon(route.route_number)} {route.route_number || 'Route ?'} → {route.destination || 'Unknown'}
        </Typography>
        {route.status && <Chip size="small" label={route.status} color={getStatusColor(route.status)} />}
        </Stack>
        <Typography variant="body2" color="text.secondary">
        Arrival: <b>{formatTime(route.arrival_time)}</b>
        </Typography>
        {route.vehicle?.nearest_stop ? (
        <Typography variant="caption" color="text.secondary">
            Vehicle near: {route.vehicle.nearest_stop}
        </Typography>
        ) : (
        <Typography variant="caption" color="text.disabled">
            Vehicle location unavailable
        </Typography>
        )}
        </Box>
    );

    return (
        <Card elevation={2}>
        <CardContent>
        <Typography variant="h6" fontWeight="bold" color="primary.main" gutterBottom>
        Nearby Stops ({stopsArray.length})
        </Typography>
        <List>
        {stopsArray.map((stop, index) => {
            const sid = normalizeId(stop);
            if (!sid) return null;
            const isSelected = sid === selectedStopId;
            return (
                <React.Fragment key={sid}>
                <ListItemButton onClick={() => handleStopClick(stop)}>
                <Box flexGrow={1}>
                <Stack direction="row" spacing={1} alignItems="center" mb={0.5}>
                <LocationOnIcon color="primary" fontSize="small" />
                <Typography fontWeight={500} noWrap>{stop.stop_name || 'Unknown Stop'}</Typography>
                </Stack>
                <Stack direction="row" justifyContent="space-between">
                <Typography variant="caption" color="text.secondary">
                Stop ID: {sid}
                </Typography>
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
                    {['inbound', 'outbound'].map((dir) => (
                        stopSchedule[dir]?.length > 0 && (
                            <Box key={dir} mb={2}>
                            <Typography variant="subtitle1" gutterBottom>{dir.charAt(0).toUpperCase() + dir.slice(1)}</Typography>
                            <List dense disablePadding>
                            {stopSchedule[dir].map((route, i) => (
                                <ListItem key={`${dir}-${i}`} disablePadding>
                                <ListItemText primary={renderRouteInfo(route)} disableTypography />
                                </ListItem>
                            ))}
                            </List>
                            </Box>
                        )
                    ))}
                    {stopSchedule.inbound?.length === 0 && stopSchedule.outbound?.length === 0 && (
                        <Typography variant="body2" color="text.secondary">No upcoming transit found.</Typography>
                    )}
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
