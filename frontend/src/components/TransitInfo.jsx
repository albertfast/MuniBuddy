// frontend/src/components/TransitInfo.jsx

import React, { useState, useCallback, useMemo, useRef, useEffect } from 'react'; 
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
// Use baseApiUrl prop passed from App.jsx
// const API_BASE_URL = import.meta.env.VITE_API_BASE ?? 'https://munibuddy.live/api/v1';

const normalizeId = (stop) => stop?.gtfs_stop_id || stop?.stop_code || stop?.stop_id;
const cleanStopCode = (stopId) => stopId?.replace(/^place_/, '').replace(/_\d+$/, '').toUpperCase();

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
const renderRouteTypeIconOriginal = (routeNumber, agency) => {
    const isBart = agency?.toLowerCase() === 'bart' || agency?.toLowerCase() === 'ba';
    const isLikelyTrain = isBart || routeNumber?.toLowerCase().includes('to') || (routeNumber && /[a-zA-Z]/.test(routeNumber)); // Combine heuristics
    const IconComponent = isLikelyTrain ? TrainIcon : DirectionsBusIcon;
    // Use inherit to pick up color from context (Typography)
    return <IconComponent color="inherit" fontSize="small" sx={{ verticalAlign: 'middle', mr: 0.5 }} />;
};

const groupScheduleEntries = (entries = []) => {
    const groupedMap = new Map();
  
    for (const entry of entries) {
      const key = `${entry.route_number}__${entry.destination}`;
      if (!groupedMap.has(key)) {
        groupedMap.set(key, {
          route_number: entry.route_number,
          destination: entry.destination,
          arrivals: [],
          is_realtime: entry.is_realtime,
          vehicle: entry.vehicle,
        });
      }
      const label = entry.status === 'Due' 
        ? '[Due]'
        : entry.minutes_until !== null
            ? (entry.minutes_until <= 15 ? `[${entry.minutes_until}]` : `[${entry.minutes_until} min]`)
            : '[Unknown]';
      groupedMap.get(key).arrivals.push(label);
    }
    return Array.from(groupedMap.values());
  };
  
// Original getNearestStopName
const getNearestStopName = async (lat, lon, baseApiUrl) => {
    if (!lat || !lon || !baseApiUrl) return ""; 
    try {
        const res = await axios.get(`${baseApiUrl}/nearby-stops`, { 
            params: { lat, lon, radius: 0.15, agency: 'muni' },
            timeout: 4000 
        });
        const stops = res.data || [];
        const seen = new Set();
        // Find first unique stop name
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
        const directionRef = (journey?.DirectionRef || "0").toLowerCase(); // Default to 0
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
            arrival_time: arrivalTimeISO || "Unknown",
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

// **VERY Simple BART Adapter** - Just makes the structure renderable
const adaptBartDataSimply = (bartData) => {
     const adapted = { inbound: [], outbound: [] };
     if (!bartData || !bartData.inbound || !bartData.outbound) return adapted;
     for (const dir of ['inbound', 'outbound']) {
         if (Array.isArray(bartData[dir])) {
             adapted[dir] = bartData[dir].map(bartRoute => {
                 const minutesUntil = typeof bartRoute.minutes_until === 'number' ? bartRoute.minutes_until : parseInt(bartRoute.arrival_time, 10);
                 if (isNaN(minutesUntil)) return null;
                 return {
                     route_number: bartRoute.route_number || "BART", destination: bartRoute.destination || "Unknown",
                     arrival_time: null, status: minutesUntil === 0 ? "Due" : `${minutesUntil} min`,
                     minutes_until: minutesUntil, is_realtime: true, vehicle: { nearest_stop: "" }
                 };
             }).filter(Boolean);
             adapted[dir].sort((a, b) => (a.minutes_until ?? Infinity) - (b.minutes_until ?? Infinity));
         }
     }
     return adapted;
};

// --- TransitInfo Component ---
const TransitInfo = ({ stops, setLiveVehicleMarkers, baseApiUrl }) => {
    const [selectedStopId, setSelectedStopId] = useState(null); // Uses original normalizeId result
    const [selectedStopObject, setSelectedStopObject] = useState(null); // Store full stop object for context
    const [stopSchedule, setStopSchedule] = useState(null);
    const [loadingSchedule, setLoadingSchedule] = useState(false);
    const [scheduleError, setScheduleError] = useState(null); // Changed from 'error' state name
    const listRef = useRef(null);
    const selectedItemRef = useRef(null);

    // Stops array from props (App.jsx handles de-duplication)
    const stopsArray = useMemo(() => Object.values(stops || {}), [stops]);

    // Caching
    const getCachedSchedule = useCallback((stopId) => { const item = SCHEDULE_CACHE[stopId]; return item && Date.now() - item.timestamp < CACHE_TTL ? item.data : null; }, []);
    const setCachedSchedule = useCallback((stopId, data) => { SCHEDULE_CACHE[stopId] = { data, timestamp: Date.now() }; }, []);

    // Scroll Effect
    useEffect(() => {
        if (selectedItemRef.current && listRef.current) {
            const scrollOptions = {
                behavior: 'smooth',
                block: window.innerWidth < 600 ? 'start' : 'nearest'
            };
            const timer = setTimeout(() => {
                selectedItemRef.current?.scrollIntoView(scrollOptions);
            }, 100);
            return () => clearTimeout(timer);
        }
    }, [selectedStopId]);

    // handleStopClick based on original logic
    const handleStopClick = useCallback(async (stopObject) => {
        // Use original normalizeId for selection state
        const currentSelectedId = normalizeId(stopObject);
        // *** FIX: Clean BART ID specifically for API call ***
        let apiStopCode = cleanStopCode(stopObject.stop_code || currentSelectedId);
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
                schedule.inbound = groupScheduleEntries(schedule.inbound);
                schedule.outbound = groupScheduleEntries(schedule.outbound);
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


    // handleRefresh based on original logic
    const handleRefreshSchedule = useCallback(async () => {
        if (!selectedStopId || !selectedStopObject) return;
        delete SCHEDULE_CACHE[selectedStopId];
        await handleStopClick(selectedStopObject);
    }, [selectedStopId, selectedStopObject, handleStopClick]);


// Use original renderRouteInfo function signature
    // Apply new CSS classes and updated icon/chip rendering
    const renderRouteInfo = (routeEntry) => {
      const agency = selectedStopObject?.agency; // Get agency from selected stop
    
      return (
        <Box className="route-info-box">
          <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1} mb={0.5}>
            <Typography
              variant="h6"
              component="div"
              className="route-title"
              noWrap
              sx={{ flexGrow: 1, mr: 1 }}
            >
              {renderRouteTypeIconOriginal(routeEntry.route_number, agency)}
              {routeEntry.route_number || "Route ?"}
              <Typography component="span" className="route-destination">
                {" "}
                → {routeEntry.destination || "Unknown"}
              </Typography>
            </Typography>
          </Stack>
    
          {/* Keep Arrival time display if arrival_time exists and is not 'Unknown' */}
          {routeEntry.arrival_time && routeEntry.arrival_time !== "Unknown" && (
            <Typography variant="body2" className="route-arrival-detail">
              Arrival: <b>{formatTime(routeEntry.arrival_time)}</b>
            </Typography>
          )}
    
          <Typography
            variant="body2"
            className={
              routeEntry.vehicle?.nearest_stop
                ? "route-vehicle-location"
                : "route-vehicle-location-unavailable"
            }
            sx={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              gap: "6px",
              mt: 0.5,
            }}
          >
            {routeEntry.vehicle?.nearest_stop ? (
              <>
                Vehicle near: {routeEntry.vehicle.nearest_stop}
                {routeEntry.arrivals?.map((a, i) => {
                  let bg = "#9e9e9e";
                  const clean = a.replace(/\[|\]/g, '').replace(' min', '');
                  const num = parseInt(clean);
                  if (a === "[Due]" || clean === "Due") bg = "#e53935";
                  else if (!isNaN(num) && num <= 5) bg = "#43a047";
                  else if (!isNaN(num) && num <= 15) bg = "#fb8c00";
    
                  return (
                    <Chip
                      key={i}
                      size="small"
                      label={clean + (i === routeEntry.arrivals.length - 1 && !isNaN(num) ? " min" : "")}
                      sx={{
                        backgroundColor: bg,
                        color: "white",
                        fontWeight: "bold",
                        fontSize: "0.7rem",
                        height: "20px",
                      }}
                    />
                  );
                })}
              </>
            ) : (
              "Vehicle location unavailable"
            )}
          </Typography>
        </Box>
      );
    };

    // --- Main Render ---
    return (
        // Apply new Card class
        <Card elevation={0} className="transit-card-custom">
            <CardContent sx={{ p: { xs: 1, sm: 1.5 }, display: 'flex', flexDirection: 'column', flexGrow: 1 }}>
                 {/* Apply new header class */}
                 <Typography className="transit-section-header" sx={{ pl: { xs: 0, sm: 1 }, flexShrink: 0 }}> Nearby Stops ({stopsArray.length}) </Typography>
                 {stopsArray.length === 0 && !loadingSchedule && ( <Typography align="center" color="text.secondary" sx={{ py: 3, flexGrow: 1, display:'flex', alignItems:'center', justifyContent:'center' }}> No stops found. </Typography> )}

                {/* Attach ref to the List */}
                <List ref={listRef} disablePadding className="nearby-stops-list" sx={{flexGrow: 1, overflowY: 'auto'}}>
                    {stopsArray.map((stop) => {
                        const sid = normalizeId(stop); // Use original ID for selection state
                        if (!sid) return null;
                        const isSelected = sid === selectedStopId;
                        const itemKey = stop.display_id_for_transit_info || stop.stop_id || sid; // Use App's ID for key

                        return (
                            <React.Fragment key={itemKey}>
                                <ListItemButton ref={isSelected ? selectedItemRef : null} onClick={() => handleStopClick(stop)} sx={{ pt: 1, pb: 1, borderRadius: '4px', '&:hover': { backgroundColor: 'action.hover' }, mb: 0.5 }} className={isSelected ? "stop-list-item stop-list-item-selected" : "stop-list-item"}>
                                    <Box flexGrow={1}>
                                        <Stack direction="row" spacing={1} alignItems="center" mb={0.25}> <LocationOnIcon color="primary" fontSize="small" /> <Typography fontWeight={500} noWrap sx={{ fontSize: '0.95rem' }}>{stop.stop_name || 'Unknown Stop'}</Typography> </Stack>
                                        <Stack direction="row" justifyContent="space-between" alignItems="center">
                                            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.75rem' }}> ID: {stop.stop_code || sid} </Typography>
                                            {/* *** SAFER toFixed Rendering *** */}
                                            {(() => {
                                                const distanceVal = stop.distance_miles; let displayDistanceLabel = null;
                                                if (distanceVal != null) { let numValue; if (typeof distanceVal === 'number') { numValue = distanceVal; } else { numValue = parseFloat(distanceVal); } if (typeof numValue === 'number' && isFinite(numValue)) { try { displayDistanceLabel = `${numValue.toFixed(3)} mi`; } catch (e) { console.error(`Error in toFixed for stop ${itemKey}:`, e); } } }
                                                return displayDistanceLabel ? (<Chip component="span" size="small" label={displayDistanceLabel} sx={{ fontSize: '0.7rem', height: '18px', mr: 1 }} />) : null;
                                            })()}
                                            {/* *** END SAFER toFixed *** */}
                                        </Stack>
                                    </Box>
                                    {isSelected ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                                </ListItemButton>

                                <Collapse in={isSelected} timeout="auto" unmountOnExit>
                                     {/* Apply minHeight and flex styles */}
                                    <Box px={{ xs: 1, sm: 1.5 }} pb={1.5} pt={1} sx={{ borderLeft: '3px solid var(--purpleLight)', ml: { xs: 0.5, sm: 1 }, mr: { xs: 0.5, sm: 1 }, mb: 1, minHeight: '150px', display: 'flex', flexDirection: 'column' }} className="stop-details-collapse">
                                        {/* Use original Refresh Button style */}
                                        <Button size="small" variant="outlined" startIcon={<RefreshIcon />} onClick={handleRefreshSchedule} sx={{ mb: 1, alignSelf: 'flex-start', textTransform: 'none', color: 'var(--purple)', '&:hover': { backgroundColor: 'var(--purpleLight)' } }} disabled={loadingSchedule}>
                                            {loadingSchedule && isSelected ? "Refreshing..." : "Refresh"}
                                        </Button>
                                        {/* Original Loading/Error/Schedule rendering */}
                                        {loadingSchedule ? (
                                            <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><CircularProgress size={28} /></Box>
                                        ) : stopSchedule ? (
                                            <>
                                                {scheduleError && <Alert severity="warning" sx={{ mb: 2, fontSize: '0.8rem' }}>{scheduleError}</Alert>}
                                                {['inbound', 'outbound'].map((dir) => (
                                                    stopSchedule[dir]?.length > 0 && (
                                                        <Box key={dir} mb={1}>
                                                            {/* Use original subtitle style */}
                                                            <Typography variant="subtitle1" gutterBottom sx={{fontSize: '0.8rem', fontWeight:'bold', color:'var(--current-grayMid-val)'}}>{dir.charAt(0).toUpperCase() + dir.slice(1)}</Typography>
                                                            <List dense disablePadding>
                                                                {stopSchedule[dir].map((routeEntry, i) => (
                                                                    <ListItem key={`${dir}-${i}`} disablePadding sx={{mb: 0.5}} className="transit-list-item-custom">
                                                                        {/* Call original render function */}
                                                                        <ListItemText primary={renderRouteInfo(routeEntry)} disableTypography />
                                                                    </ListItem>
                                                                ))}
                                                            </List>
                                                        </Box>
                                                    )
                                                ))}
                                                {(stopSchedule.inbound?.length === 0 && stopSchedule.outbound?.length === 0) && (
                                                    <Typography className="transit-empty" sx={{ fontSize: '0.9rem', mt: 'auto', pt: 2 }}>No upcoming transit found.</Typography>
                                                )}
                                            </>
                                        ) : ( // No schedule data available
                                            <Typography variant="body2" color="text.secondary" sx={{mt:'auto', pt: 2, textAlign:'center'}}>No schedule available.</Typography>
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

