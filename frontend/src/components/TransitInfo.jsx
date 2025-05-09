// frontend/src/components/TransitInfo.jsx

import React, { useState, useCallback, useMemo, useRef, useEffect } from 'react'; // Added useRef, useEffect
import {
    Card, CardContent, Typography, List, ListItem, ListItemText, ListItemButton,
    Box, Collapse, CircularProgress, Stack, Chip, Button, Alert
} from '@mui/material';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import TrainIcon from '@mui/icons-material/Train';
import { bartStations, bartRoutes, getRouteDetails } from '../data/bartData'; 
import LocationOnIcon from '@mui/icons-material/LocationOn';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import RefreshIcon from '@mui/icons-material/Refresh';
import axios from 'axios';
// Assuming style.css is imported in App.jsx

// --- Constants and Utilities (From your original code) ---
const SCHEDULE_CACHE = {};
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes cache
const API_TIMEOUT = 50000; // 50 seconds timeout
// Use baseApiUrl prop passed from App.jsx
// const API_BASE_URL = import.meta.env.VITE_API_BASE ?? 'https://munibuddy.live/api/v1';

// Original normalizeId - used for selection state and internal logic
const normalizeId = (stop) => stop?.gtfs_stop_id || stop?.stop_code || stop?.stop_id;
const normalizeIdForSelection = normalizeId;

const normalizeIdForApi = (stop) => {
    const raw = normalizeIdForSelection(stop);
    return raw.replace(/^place_/, '').replace(/_\d+$/, '');
  };

  const processSiriVisits = async (visits, agency, apiBaseUrl) => {
    return {
      inbound: [],
      outbound: visits || [],
    };
  };  

// Original formatTime
const formatTime = (isoTime) => {
    if (!isoTime || isoTime === "Unknown") return "Unknown";
    try {
        const date = new Date(isoTime);
        return isNaN(date.getTime()) ? isoTime : date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true, timeZone: 'America/Los_Angeles' });
    } catch { return isoTime; }
};

// Original getStatusColor based on status string
const getStatusColorFromString = (status = '') => {
    const s = status.toLowerCase();
    if (s === 'due') return 'error';
    if (s.includes('min')) {
        const mins = parseInt(s, 10);
        if (!isNaN(mins)) {
             if (mins <= 5) return 'success';
             if (mins <= 15) return 'warning';
        }
    }
    if (s.includes('late')) return 'error';
    if (s.includes('early')) return 'warning';
    return 'default';
};

// Original renderIcon, adapted for consistent color
const renderRouteTypeIcon = (routeNumber, agency) => {
    const isBart = agency?.toLowerCase() === 'bart' || agency?.toLowerCase() === 'ba';
    const isLikelyTrain = isBart || routeNumber?.toLowerCase().includes('to') || (routeNumber && /[a-zA-Z]/.test(routeNumber));
    const IconComponent = isLikelyTrain ? TrainIcon : DirectionsBusIcon;
    // Use inherit color
    return <IconComponent color="inherit" fontSize="small" sx={{ verticalAlign: 'middle', mr: 0.5 }} />;
};


// Original getNearestStopName
const getNearestStopName = async (lat, lon, baseApiUrl) => {
    if (!lat || !lon || !baseApiUrl) return "";
    // Removed simple cache for stability for now, can be added back later
    try {
        const res = await axios.get(`${baseApiUrl}/nearby-stops`, { params: { lat, lon, radius: 0.15, agency: 'muni' }, timeout: 4000 });
        const stops = res.data || [];
        const seen = new Set();
        const firstUnique = stops.find(s => { if (s.stop_name && !seen.has(s.stop_name)) { seen.add(s.stop_name); return true; } return false; });
        return firstUnique?.stop_name?.trim() || "";
    } catch (err) {
        console.warn('[nearestStopName] Error:', err.message);
        return "";
    }
};

// Original normalizeSiriData
const normalizeSiriData = async (visits = [], baseApiUrl) => {
    const grouped = { inbound: [], outbound: [] };
    for (const visit of visits) {
        const journey = visit?.MonitoredVehicleJourney; if (!journey) continue;
        const call = journey?.MonitoredCall || {};
        const directionRef = (journey?.DirectionRef || "0").toLowerCase();
        const arrivalTimeISO = call?.ExpectedArrivalTime || call?.AimedArrivalTime;
        const arrivalDate = arrivalTimeISO ? new Date(arrivalTimeISO) : null;
        const now = new Date();
        const minutesUntil = arrivalDate ? Math.max(0, Math.round((arrivalDate - now) / 60000)) : null;
        const lat = journey?.VehicleLocation?.Latitude || "";
        const lon = journey?.VehicleLocation?.Longitude || "";
        const nearestStop = await getNearestStopName(lat, lon, baseApiUrl); // Call helper

        const entry = {
            route_number: journey?.LineRef ? `${journey.LineRef} ${journey?.PublishedLineName ?? ''}`.trim() : journey?.PublishedLineName ?? "Unknown Line",
            destination: call?.DestinationDisplay || journey?.DestinationName || "Unknown Dest.",
            arrival_time: arrivalTimeISO, // Keep ISO
            status: minutesUntil !== null ? (minutesUntil === 0 ? "Due" : `${minutesUntil} min`) : "Unknown",
            minutes_until: minutesUntil,
            is_realtime: !!call?.ExpectedArrivalTime,
            vehicle: { lat, lon, nearest_stop: nearestStop || "" }
        };
        const directionKey = (directionRef === "0" || directionRef === "inbound" || journey?.DirectionName?.toLowerCase().includes("inbound")) ? 'inbound' : 'outbound';
        grouped[directionKey].push(entry);
    }
    grouped.inbound.sort((a,b) => (a.minutes_until ?? Infinity) - (b.minutes_until ?? Infinity));
    grouped.outbound.sort((a,b) => (a.minutes_until ?? Infinity) - (b.minutes_until ?? Infinity));
    return grouped;
};

// **SIMPLE BART Adapter for original render function**
const adaptBartDataSimply = (bartData) => {
     const adapted = { inbound: [], outbound: [] };
     if (!bartData || !bartData.inbound || !bartData.outbound) return adapted;
     for (const dir of ['inbound', 'outbound']) {
         if (Array.isArray(bartData[dir])) {
             adapted[dir] = bartData[dir].map(bartRoute => {
                 const minutesUntil = typeof bartRoute.minutes_until === 'number' ? bartRoute.minutes_until : parseInt(bartRoute.arrival_time, 10);
                 if (isNaN(minutesUntil)) return null;
                 return {
                     route_number: bartRoute.route_number || "BART",
                     destination: bartRoute.destination || "Unknown",
                     arrival_time: null, // No ISO time
                     status: minutesUntil === 0 ? "Due" : `${minutesUntil} min`, // Status string
                     minutes_until: minutesUntil,
                     is_realtime: true,
                     vehicle: { nearest_stop: "" } // No vehicle info
                 };
             }).filter(Boolean);
             adapted[dir].sort((a, b) => (a.minutes_until ?? Infinity) - (b.minutes_until ?? Infinity));
         }
     }
     return adapted;
};


// --- TransitInfo Component ---
const TransitInfo = ({ stops, setLiveVehicleMarkers, baseApiUrl, setBartVisualizations }) => { // ADD setBartVisualizations PROP
    const [selectedStopId, setSelectedStopId] = useState(null);
    const [selectedStopObject, setSelectedStopObject] = useState(null);
    const [stopSchedule, setStopSchedule] = useState(null); // Processed schedule (SIRI or adapted BART)
    const [loadingSchedule, setLoadingSchedule] = useState(false);
    const [scheduleError, setScheduleError] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const stopsArray = useMemo(() => {
        const raw = Array.isArray(stops) ? stops : Object.values(stops || {});
        return raw.filter(s => {
            const id = s.stop_code || s.stop_id || s.gtfs_stop_id;
            return typeof id === 'string' && !id.startsWith("place_");
          });
      }, [stops]);      
    console.log("⏳ Raw stops:", stops);
    const listRef = useRef(null);
    const selectedItemRef = useRef(null);

    const getCachedSchedule = useCallback((stopId) => { /* ... */ }, []);
    const setCachedSchedule = useCallback((stopId, data) => { /* ... */ }, []);

    // --- Scroll Effect ---
    // useEffect(() => { /* ... (same as before) ... */ }, [selectedStopId]);

    // --- BART Visualization Calculation ---
    // This effect runs when the schedule for a selected stop is loaded
    useEffect(() => {
        const visualizations = []; // Array to hold { path: [latLng,...], marker: { position, icon, title } }
        if (stopSchedule && selectedStopObject && selectedStopObject.agency?.toLowerCase().includes('bart')) {
            const selectedStationAbbr = normalizeIdForApi(selectedStopObject); // e.g., "POWL"

            ['inbound', 'outbound'].forEach(dir => {
                if (stopSchedule[dir]) {
                    stopSchedule[dir].forEach((entry, index) => {
                         // We need to figure out the line and previous station
                        const destinationAbbr = entry.destination ? Object.keys(bartStations).find(key => bartStations[key].name === entry.destination) : null;
                        const routeNum = entry.route_number; // e.g., "MLBR", "DALY"

                        if (!routeNum || !selectedStationAbbr) return;

                        // Find the line key (e.g., "RED-S") - This logic might need refinement
                        // It assumes route_number corresponds to the *terminal* station abbr
                        let foundLineKey = null;
                        for (const lineKey in bartRoutes) {
                            const route = bartRoutes[lineKey];
                            // Check if the line contains the selected station AND the terminal station matches the route number
                            if (route.stations.includes(selectedStationAbbr) && route.stations[route.stations.length - 1] === routeNum) {
                                foundLineKey = lineKey;
                                break;
                            }
                            // Add more checks if route_number isn't always the terminal
                        }

                        if (!foundLineKey) {
                            console.warn(`Could not determine line key for route ${routeNum} to ${entry.destination} at ${selectedStationAbbr}`);
                            return;
                        }

                        const routeDetails = getRouteDetails(foundLineKey);
                        const stationList = routeDetails.stations;
                        const currentIndex = stationList.indexOf(selectedStationAbbr);

                        if (currentIndex > 0) { // Ensure there is a previous station
                            const prevStationAbbr = stationList[currentIndex - 1];
                            const prevStationCoords = bartStations[prevStationAbbr];
                            const currentStationCoords = bartStations[selectedStationAbbr];

                            if (prevStationCoords && currentStationCoords) {
                                // --- Simple Visualization: Marker at previous station, line between prev and current ---
                                const pathCoords = [
                                    { lat: prevStationCoords.lat, lng: prevStationCoords.lng },
                                    { lat: currentStationCoords.lat, lng: currentStationCoords.lng }
                                ];

                                // Marker at the *previous* station to indicate the train is on this segment
                                const marker = {
                                    position: { lat: prevStationCoords.lat, lng: prevStationCoords.lng },
                                    icon: { // Simple colored dot
                                        path: window.google?.maps?.SymbolPath?.CIRCLE, // Requires google maps loaded
                                        scale: 6,
                                        fillColor: routeDetails.color || '#FFFF00', // Use line color or yellow fallback
                                        fillOpacity: 1,
                                        strokeWeight: 1,
                                        strokeColor: '#000000'
                                    },
                                    title: `Estimated ${routeNum} train to ${entry.destination} (arriving in ${entry.minutes_until} min)`,
                                    id: `bart-viz-${dir}-${index}`
                                };

                                visualizations.push({ path: pathCoords, marker: marker, color: routeDetails.color || '#808080' });

                            }
                        }
                    });
                }
            });
        }
        // Call the setter function passed from App.jsx
        if (setBartVisualizations) {
            setBartVisualizations(visualizations);
        }
    // Run when schedule or selected stop changes
    }, [stopSchedule, selectedStopObject, setBartVisualizations]);


    // --- handleStopClick (Fetch and process data) ---
    const handleStopClick = useCallback(async (stopObject) => {
        // Use original normalizeId for selection state
        const currentSelectedId = normalizeId(stopObject);
        // *** FIX: Clean BART ID specifically for API call ***
        let apiStopCode = stopObject.stop_code || currentSelectedId;
        const agency = stopObject.agency?.toLowerCase();
        if ((agency === 'bart' || agency === 'ba') && apiStopCode) {
             if (apiStopCode.includes('_')) { apiStopCode = apiStopCode.split('_')[0]; }
             if (apiStopCode.toLowerCase().startsWith('place_') || apiStopCode.toLowerCase().startsWith('place-')) { apiStopCode = apiStopCode.substring(6); }
             apiStopCode = apiStopCode.toUpperCase();
        }

        selectedItemRef.current = null;

        // Toggle selection
        if (currentSelectedId === selectedStopId) {
            setSelectedStopId(null); setSelectedStopObject(null); setStopSchedule(null); setScheduleError(null);
            return;
        }

        setSelectedStopId(currentSelectedId);
        setSelectedStopObject(stopObject); // Store for context
        setStopSchedule(null); setScheduleError(null); setLoadingSchedule(true);

        // Check cache using the original selected ID
        const cached = getCachedSchedule(currentSelectedId);
        if (cached) { setStopSchedule(cached); setLoadingSchedule(false); return; }

        // Fetch from API
        try {
             // Ensure apiStopCode is valid before making the call
             if (!apiStopCode) {
                throw new Error("Missing valid stop code for API call.");
             }
             const predictionURL = (agency === "bart" || agency === "ba")
                ? `${baseApiUrl}/bart-positions/by-stop?stopCode=${apiStopCode}&agency=${agency}` // Use cleaned apiStopCode
                : `${baseApiUrl}/bus-positions/by-stop?stopCode=${apiStopCode}&agency=${agency}`; // Use cleaned apiStopCode

            console.log(`[TransitInfo STABLE BASE] Fetching schedule for ID: ${currentSelectedId} (API Code: ${apiStopCode}, Agency: ${agency})`);
            const res = await axios.get(predictionURL, { timeout: API_TIMEOUT });
            const responseData = res.data?.realtime || res.data; // Original way to get data
            const siriVisits = responseData?.ServiceDelivery?.StopMonitoringDelivery?.MonitoredStopVisit;

            let schedule;
            // Use original logic for processing
            if (Array.isArray(siriVisits)) {
                console.log("[TransitInfo STABLE BASE] Processing SIRI data...");
                schedule = await normalizeSiriData(siriVisits, baseApiUrl);
            }
            // ** MODIFICATION: Handle BART pre-grouped data simply **
            else if ((agency === "bart" || agency === "ba") && responseData && responseData.inbound && responseData.outbound) {
                 console.log("[TransitInfo STABLE BASE] Adapting pre-grouped BART data...");
                 schedule = adaptBartDataSimply(responseData);
            }
            else { // Treat anything else (including non-array 'visits' or direct data) as potentially unusable for now
                 console.warn(`[TransitInfo STABLE BASE] No processable schedule data found for ${currentSelectedId}. Response data:`, responseData);
                 schedule = { inbound: [], outbound: [] }; // Default to empty
                 // Set error only if there was response data but it wasn't processable
                 if(responseData) {
                    setScheduleError('Could not understand schedule format.');
                 } else {
                     setScheduleError('No schedule data received.');
                 }
            }

             // Final check
             if (!schedule || !schedule.inbound || !schedule.outbound) {
                 schedule = { inbound: [], outbound: [] };
             }

            setCachedSchedule(currentSelectedId, schedule);
            setStopSchedule(schedule);

            // Original fetchVehiclePositions call (optional)
            // if (setLiveVehicleMarkers) { await fetchVehiclePositions(stopObject); }

        } catch (err) {
            console.error(`[TransitInfo STABLE BASE] Failed fetch/process for ${currentSelectedId}:`, err);
             // *** Use setScheduleError ***
            setScheduleError(`Failed to load schedule. ${err.message}`);
            setStopSchedule({ inbound: [], outbound: [] }); // Set empty schedule
        } finally {
            setLoadingSchedule(false);
        }
    // Keep original dependencies, add baseApiUrl
    }, [selectedStopId, selectedStopObject, getCachedSchedule, setCachedSchedule, baseApiUrl, setLiveVehicleMarkers]);

    // --- handleRefreshSchedule ---
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

    // --- Render Function for Individual Route Entries (Original Logic) ---
    const renderRouteEntry = (routeEntry) => { 
        const chipColor = getStatusColorFromString(routeEntry.status);
        const agency = selectedStopObject?.agency;
        return ( <Box className="route-info-box"> <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1} mb={0.5}> <Typography variant="h6" component="div" className="route-title" noWrap sx={{ flexGrow: 1, mr: 1 }}> {renderRouteTypeIcon(routeEntry.route_number, agency)} {routeEntry.route_number || 'Route ?'} <Typography component="span" className="route-destination"> {' '}→ {routeEntry.destination || 'Unknown'} </Typography> </Typography> {routeEntry.status && ( <Chip size="small" label={routeEntry.status} color={chipColor} sx={{ fontWeight: 'bold', fontSize: '0.75rem', flexShrink: 0 }}/> )} </Stack> <Typography variant="body2" className="route-arrival-detail"> Arrival: <b>{formatTime(routeEntry.arrival_time)}</b> </Typography> {routeEntry.vehicle?.nearest_stop ? ( <Typography variant="caption" className="route-vehicle-location"> Vehicle near: {routeEntry.vehicle.nearest_stop} </Typography> ) : ( routeEntry.is_realtime && routeEntry.minutes_until != null && <Typography variant="caption" className="route-vehicle-location-unavailable"> Vehicle location unavailable </Typography> )} </Box> );
    };

    // --- Main Render ---
    return (
        <Card elevation={0} className="transit-card-custom">
            <CardContent sx={{ p: { xs: 1, sm: 1.5 }, display: 'flex', flexDirection: 'column', flexGrow: 1 }}>
                <Typography className="transit-section-header" sx={{ pl: { xs: 0, sm: 1 }, flexShrink: 0 }}> Nearby Stops ({stopsArray.length}) </Typography>
                {stopsArray.length === 0 && !loadingSchedule && ( <Typography align="center" color="text.secondary" sx={{ py: 3, flexGrow: 1, display:'flex', alignItems:'center', justifyContent:'center' }}> No stops found. </Typography> )}
                <List ref={listRef} disablePadding className="nearby-stops-list" sx={{flexGrow: 1, overflowY: 'auto'}}>
                    {stopsArray.map((stop) => {
                        const displayId = normalizeIdForSelection(stop); // ID used by App.jsx
                        if (!displayId) return null;
                        const isSelected = selectedStopId === displayId;
                        const itemKey = stop.original_stop_id_for_key || displayId;

                        return (
                            <React.Fragment key={itemKey}>
                                <ListItemButton ref={isSelected ? selectedItemRef : null} onClick={() => handleStopClick(stop)} sx={{ pt: 1, pb: 1, borderRadius: '4px', '&:hover': { backgroundColor: 'action.hover' }, mb: 0.5 }} className={isSelected ? "stop-list-item stop-list-item-selected" : "stop-list-item"}>
                                    <Box flexGrow={1}>
                                        <Stack direction="row" spacing={1} alignItems="center" mb={0.25}> <LocationOnIcon color="primary" fontSize="small" /> <Typography fontWeight={500} noWrap sx={{ fontSize: '0.95rem' }}>{stop.stop_name || 'Unknown Stop'}</Typography> </Stack>
                                        <Stack direction="row" justifyContent="space-between" alignItems="center">
                                            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.75rem' }}> ID: {stop.stop_code || displayId.replace(/-bart$/i, '').replace(/-muni$/i, '')} </Typography>
                                            {/* SAFER toFixed Rendering */}
                                            {(() => { const d=stop.distance_miles; let l=null; if(d!=null){let n; if(typeof d==='number'){n=d;}else{n=parseFloat(d);} if(typeof n==='number'&&isFinite(n)){try{l=`${n.toFixed(3)} mi`;}catch(e){console.error(`Error in toFixed for stop ${itemKey}:`, e);}}} return l?(<Chip component="span" size="small" label={l} sx={{fontSize:'0.7rem',height:'18px',mr:1}}/>):null; })()}
                                        </Stack>
                                    </Box>
                                    {isSelected ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                                </ListItemButton>
                                <Collapse in={isSelected} timeout="auto" unmountOnExit>
                                    <Box px={{ xs: 1, sm: 1.5 }} pb={1.5} pt={1} sx={{ borderLeft: '3px solid var(--purpleLight)', ml: { xs: 0.5, sm: 1 }, mr: { xs: 0.5, sm: 1 }, mb: 1, minHeight: '150px', display: 'flex', flexDirection: 'column' }} className="stop-details-collapse">
                                        <Button startIcon={<RefreshIcon />} onClick={handleRefreshSchedule} disabled={loadingSchedule} size="small" sx={{ mb: 1.5, textTransform: 'none', color: 'var(--purple)', '&:hover': { backgroundColor: 'var(--purpleLight)' }, alignSelf: 'flex-start' }}> {loadingSchedule ? "Refreshing..." : "Refresh"} </Button>
                                        {/* Original Loading/Error/Schedule rendering logic */}
                                        {loadingSchedule && isSelected ? ( <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><CircularProgress size={28} /></Box> )
                                        : scheduleError && isSelected ? ( <Alert severity="error" sx={{ fontSize: '0.85rem' }}>{scheduleError}</Alert> )
                                        : stopSchedule && isSelected ? (
                                            <>
                                                {['inbound', 'outbound'].map((dir) => (
                                                    stopSchedule[dir]?.length > 0 && (
                                                        <Box key={dir} mb={1}>
                                                            <Typography variant="subtitle1" gutterBottom sx={{fontSize: '0.8rem', fontWeight:'bold', color:'var(--current-grayMid-val)'}}>{dir.charAt(0).toUpperCase() + dir.slice(1)}</Typography>
                                                            <List dense disablePadding>
                                                                {/* Use original render function */}
                                                                {stopSchedule[dir].map((routeEntry, i) => (
                                                                    <ListItem key={`${dir}-${i}`} disablePadding sx={{mb: 0.5}} className="transit-list-item-custom">
                                                                        <ListItemText primary={renderRouteEntry(routeEntry)} disableTypography />
                                                                    </ListItem>
                                                                ))}
                                                            </List>
                                                        </Box>
                                                    )
                                                ))}
                                                {(stopSchedule.inbound?.length === 0 && stopSchedule.outbound?.length === 0) && ( <Typography className="transit-empty" sx={{ fontSize: '0.9rem', mt: 'auto', pt: 2 }}>No upcoming transit found.</Typography> )}
                                            </>
                                        ) : isSelected && ( <Typography variant="body2" color="text.secondary" sx={{mt:'auto', pt: 2, textAlign:'center'}}>No schedule available.</Typography> )}
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