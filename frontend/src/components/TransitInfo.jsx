
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
const API_TIMEOUT = 50000;
const API_BASE_URL = import.meta.env.VITE_API_BASE ?? 'https://munibuddy.live/api/v1';

const normalizeId = (stop) => stop?.gtfs_stop_id || stop?.stop_code || stop?.stop_id;

const normalizeStopInfo = (stop) => {
    const stopCode = stop.stop_code || stop.stop_id;
    const agency = stop.agency?.toLowerCase() || (stopCode?.length <= 5 ? "bart" : "muni");
    return { stopCode, agency };
};

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
    const s = status.toLowerCase();
    if (s.includes('late')) return 'error';
    if (s.includes('early')) return 'warning';
    return 'success';
};

const renderIcon = (routeNumber) =>
routeNumber?.toLowerCase().includes('to')
? <TrainIcon color="primary" fontSize="small" />
: <DirectionsBusIcon color="secondary" fontSize="small" />;

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
                        const stopName = await getNearestStopName(route.vehicle.lat, route.vehicle.lon);
                        updates[key] = stopName;
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

    const fetchVehiclePositions = async (stop) => {
        const { stopCode, agency } = normalizeStopInfo(stop);
        const endpoint = agency === "bart"
            ? `/bart-positions/by-stop?stopCode=${stopCode}&agency=${agency}`
            : `/bus-positions/by-stop?stopCode=${stopCode}&agency=${agency}`;

        console.log(`[fetchVehiclePositions] stopCode=${stopCode}, agency=${agency}, endpoint=${endpoint}`);
        try {
            const res = await axios.get(`${API_BASE_URL}${endpoint}`);
            console.log('[fetchVehiclePositions] response:', res.data);
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
            console.warn(`[fetchVehiclePositions] error for ${stopCode} (${agency}):`, err.message);
        }
    };

    const handleStopClick = useCallback(async (stop) => {
        const stopId = normalizeId(stop);
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

        const { stopCode, agency } = normalizeStopInfo(stop);
        const predictionURL = agency === "bart"
            ? `/bart-positions/by-stop?stopCode=${stopCode}&agency=${agency}`
            : `/bus-positions/by-stop?stopCode=${stopCode}&agency=${agency}`;

        console.log(`[handleStopClick] stopCode=${stopCode}, agency=${agency}, predictionURL=${predictionURL}`);
        try {
            const res = await axios.get(`${API_BASE_URL}${predictionURL}`, { timeout: API_TIMEOUT });
            console.log('[handleStopClick] response:', res.data);
            const data = res.data?.realtime || res.data;
            await fetchVehiclePositions(stop);
            setCachedSchedule(stopId, data);
            setStopSchedule(data);
        } catch (err) {
            setError('Failed to fetch predictions. Try again.');
            console.warn(`[handleStopClick] failed to fetch predictions for ${stopCode}:`, err.message);
            setStopSchedule({ inbound: [], outbound: [] });
        } finally {
            setLoading(false);
        }
    }, [selectedStopId, getCachedSchedule, setCachedSchedule]);

    const getNearestStopName = async (lat, lon) => {
        try {
            const res = await axios.get(`${API_BASE_URL}/nearby-stops`, {
                params: { lat, lon, radius: 0.15, agency: 'muni' },
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
            if (uniqueStops.length > 0) {
                return uniqueStops[0].stop_name?.trim() ?? 'Unknown stop';
            }
        } catch (err) {
            console.warn('[getNearestStopName] error:', err.message);
        }
        return 'Unknown stop';
    };

    return <div>DEBUG JSX loaded. Add full UI here if needed.</div>;
};

export default TransitInfo;
