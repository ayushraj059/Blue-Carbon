import React, { useState, useEffect, useRef, useCallback } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet-draw";
import { mapSnapshot, analyzeImage } from "../api/client";

// Fix Leaflet default marker icon paths broken by webpack
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: require("leaflet/dist/images/marker-icon-2x.png"),
  iconUrl: require("leaflet/dist/images/marker-icon.png"),
  shadowUrl: require("leaflet/dist/images/marker-shadow.png"),
});

const MAP_STYLE = { width: "100%", height: "440px", borderRadius: "12px" };
const INDIA_CENTER = [13.5, 80.3]; // Bay of Bengal coast default
const DRAW_COLOR = "#22c55e";

function calcAreaHectares(coords) {
  const n = coords.length;
  if (n < 3) return 0;
  const R = 6371000;
  let area = 0;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    const lat1 = (coords[i].lat * Math.PI) / 180;
    const lng1 = (coords[i].lng * Math.PI) / 180;
    const lat2 = (coords[j].lat * Math.PI) / 180;
    const lng2 = (coords[j].lng * Math.PI) / 180;
    area += (lng2 - lng1) * (2 + Math.sin(lat1) + Math.sin(lat2));
  }
  return parseFloat(((Math.abs(area) * R * R) / 2 / 10000).toFixed(2));
}

async function nominatimReverseGeocode(lat, lng) {
  try {
    const resp = await fetch(
      `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json&zoom=10`,
      { headers: { "User-Agent": "BlueCarbonRegistry/1.0" } }
    );
    const data = await resp.json();
    const addr = data.address || {};
    return (
      addr.city || addr.town || addr.village || addr.county ||
      addr.state || data.display_name?.split(",")[0] || `Site ${lat.toFixed(4)}N`
    );
  } catch {
    return `Coastal Site ${lat.toFixed(4)}N`;
  }
}

function DrawControl({ onPolygonComplete }) {
  const map = useMap();
  const drawnItems = useRef(new L.FeatureGroup());

  useEffect(() => {
    const group = drawnItems.current;
    map.addLayer(group);

    const drawControl = new L.Control.Draw({
      position: "topright",
      draw: {
        polygon: {
          allowIntersection: false,
          showArea: true,
          shapeOptions: { color: DRAW_COLOR, weight: 2, fillOpacity: 0.2 },
        },
        rectangle: {
          shapeOptions: { color: DRAW_COLOR, weight: 2, fillOpacity: 0.2 },
        },
        circle: false,
        polyline: false,
        marker: false,
        circlemarker: false,
      },
      edit: { featureGroup: group, remove: true },
    });
    map.addControl(drawControl);

    const onCreate = async (e) => {
      group.clearLayers();
      group.addLayer(e.layer);

      const raw = e.layer.getLatLngs()[0];
      const coords = raw.map((ll) => ({ lat: ll.lat, lng: ll.lng }));
      const area = calcAreaHectares(coords);
      const center = {
        lat: coords.reduce((s, c) => s + c.lat, 0) / coords.length,
        lng: coords.reduce((s, c) => s + c.lng, 0) / coords.length,
      };
      const location = await nominatimReverseGeocode(center.lat, center.lng);
      onPolygonComplete(coords, area, location);
    };

    map.on(L.Draw.Event.CREATED, onCreate);
    return () => {
      map.removeControl(drawControl);
      map.removeLayer(group);
      map.off(L.Draw.Event.CREATED, onCreate);
    };
  }, [map, onPolygonComplete]);

  return null;
}

export default function MapPicker({ onPipelineStarted }) {
  const [mode, setMode] = useState("map");

  // Map mode state
  const [polygonCoords, setPolygonCoords] = useState([]);
  const [areaHectares, setAreaHectares] = useState(0);
  const [locationName, setLocationName] = useState("");

  // Image upload mode state
  const [imageFile, setImageFile] = useState(null);
  const [manualLocation, setManualLocation] = useState("");
  const [manualArea, setManualArea] = useState("");

  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");

  const onPolygonComplete = useCallback((coords, area, location) => {
    setPolygonCoords(coords);
    setAreaHectares(area);
    setLocationName(location);
    setError("");
  }, []);

  const handleAnalyzeMap = async () => {
    if (polygonCoords.length < 3) {
      setError("Draw a polygon on the map first using the toolbar (top right).");
      return;
    }
    setAnalyzing(true);
    setError("");
    try {
      const res = await mapSnapshot({
        polygon_coords: polygonCoords,
        area_hectares: areaHectares,
        location: locationName || undefined,
      });
      onPipelineStarted(res.data.run_id, res.data.message);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Analysis failed. Check backend is running on port 8000.");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleAnalyzeImage = async () => {
    if (!imageFile || !manualLocation || !manualArea) {
      setError("Please provide an image, location name, and area.");
      return;
    }
    setAnalyzing(true);
    setError("");
    try {
      const res = await analyzeImage(imageFile, manualLocation, parseFloat(manualArea));
      onPipelineStarted(res.data.run_id, res.data.message);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Analysis failed. Check backend is running on port 8000.");
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Mode toggle */}
      <div className="flex gap-2 bg-gray-100 rounded-lg p-1">
        <button
          onClick={() => setMode("map")}
          className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
            mode === "map" ? "bg-white shadow text-green-700" : "text-gray-500 hover:text-gray-700"
          }`}
        >
          🗺️ Draw on Map
        </button>
        <button
          onClick={() => setMode("image")}
          className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors ${
            mode === "image" ? "bg-white shadow text-green-700" : "text-gray-500 hover:text-gray-700"
          }`}
        >
          🛰️ Upload Satellite Image
        </button>
      </div>

      {/* ── MAP MODE ── */}
      {mode === "map" && (
        <>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800">
            <strong>How to use:</strong> Navigate to your coastal site on the satellite map →
            click the <strong>polygon icon</strong> (top-right toolbar) → draw around your site →
            click the first point to close the polygon.
          </div>

          <MapContainer
            center={INDIA_CENTER}
            zoom={8}
            style={MAP_STYLE}
            scrollWheelZoom={true}
          >
            {/* Esri World Imagery satellite tiles — FREE, no API key */}
            <TileLayer
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
              attribution='Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
              maxZoom={19}
            />
            {/* Labels overlay so place names show on satellite view */}
            <TileLayer
              url="https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
              attribution=""
              opacity={0.6}
            />
            <DrawControl onPolygonComplete={onPolygonComplete} />
          </MapContainer>

          {polygonCoords.length >= 3 ? (
            <div className="bg-green-50 border border-green-200 rounded-xl p-4 space-y-3">
              <p className="text-green-800 text-sm font-medium">
                ✓ Polygon drawn — {areaHectares} hectares detected
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-gray-500 font-medium">Location (auto-detected)</label>
                  <input
                    className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-green-400 outline-none"
                    value={locationName}
                    onChange={(e) => setLocationName(e.target.value)}
                    placeholder="Detected via OpenStreetMap..."
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-500 font-medium">Area (hectares)</label>
                  <input
                    className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-green-400 outline-none"
                    value={areaHectares}
                    onChange={(e) => setAreaHectares(parseFloat(e.target.value) || 0)}
                    type="number"
                    step="0.1"
                  />
                </div>
              </div>
              <button
                onClick={handleAnalyzeMap}
                disabled={analyzing}
                className="w-full py-3 bg-green-600 text-white rounded-lg font-semibold hover:bg-green-700 disabled:opacity-50 transition-colors"
              >
                {analyzing
                  ? "Fetching satellite image & analyzing with Gemini..."
                  : `Analyze ${areaHectares} ha with AI → Register on Blockchain`}
              </button>
            </div>
          ) : (
            <p className="text-center text-xs text-gray-400 mt-1">
              Use the pentagon/rectangle tool in the top-right map toolbar to draw your site boundary.
              Area and location will be auto-calculated.
            </p>
          )}
        </>
      )}

      {/* ── IMAGE UPLOAD MODE ── */}
      {mode === "image" && (
        <div className="space-y-4">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800">
            <strong>How to use:</strong> Take a screenshot from Google Earth or open Google Maps
            satellite view → screenshot your coastal site → upload below. Gemini Vision will analyze it.
          </div>

          <div
            className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center cursor-pointer hover:border-green-400 transition-colors"
            onClick={() => document.getElementById("sat-img-input").click()}
          >
            {imageFile ? (
              <div className="space-y-2">
                <img
                  src={URL.createObjectURL(imageFile)}
                  alt="preview"
                  className="max-h-52 mx-auto rounded-lg object-cover shadow"
                />
                <p className="text-sm text-green-700 font-medium">{imageFile.name}</p>
                <p className="text-xs text-gray-400">{(imageFile.size / 1024).toFixed(0)} KB</p>
              </div>
            ) : (
              <>
                <div className="text-5xl mb-2">🛰️</div>
                <p className="font-medium text-gray-700">Drop satellite/aerial image here</p>
                <p className="text-xs text-gray-400 mt-1">
                  Screenshot from Google Earth, Google Maps, Sentinel-2, Bhuvan — any aerial image works
                </p>
              </>
            )}
            <input
              id="sat-img-input"
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => { setImageFile(e.target.files[0]); setError(""); }}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-500 font-medium">Location Name *</label>
              <input
                className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-green-400 outline-none"
                placeholder="e.g. Sundarbans, Bhitarkanika..."
                value={manualLocation}
                onChange={(e) => setManualLocation(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 font-medium">Site Area (hectares) *</label>
              <input
                className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-green-400 outline-none"
                placeholder="e.g. 150.5"
                type="number"
                step="0.1"
                value={manualArea}
                onChange={(e) => setManualArea(e.target.value)}
              />
            </div>
          </div>

          <p className="text-xs text-gray-400">
            Tip: Measure area by right-clicking in Google Maps → "Measure distance" → draw polygon.
          </p>

          <button
            onClick={handleAnalyzeImage}
            disabled={analyzing || !imageFile || !manualLocation || !manualArea}
            className="w-full py-3 bg-green-600 text-white rounded-lg font-semibold hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            {analyzing
              ? "Analyzing with Gemini Vision..."
              : "Analyze Image with AI → Register Carbon Credits"}
          </button>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">
          {error}
        </div>
      )}
    </div>
  );
}
