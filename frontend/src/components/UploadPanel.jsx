import React, { useState, useRef } from "react";
import { uploadCSV } from "../api/client";

const SAMPLE_ROWS = [
  { site_id: "SB-001", location: "Sundarbans", vegetation_density: 0.82, soil_carbon_pct: 8.4, water_salinity: 28.5, area_hectares: 120, measurement_date: "2024-01-15" },
  { site_id: "CL-002", location: "Chilika", vegetation_density: 0.65, soil_carbon_pct: 5.2, water_salinity: 22.0, area_hectares: 85, measurement_date: "2024-01-16" },
];

export default function UploadPanel({ onUploadSuccess }) {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef();

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f && f.name.endsWith(".csv")) setFile(f);
    else setError("Only CSV files are accepted.");
  };

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    setError("");
    try {
      const res = await uploadCSV(file);
      onUploadSuccess(res.data.run_id);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Upload failed. Check backend is running on port 8000.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div
        className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
          dragging ? "border-green-500 bg-green-50" : "border-gray-300 hover:border-green-400"
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current.click()}
      >
        <div className="text-5xl mb-3">🌿</div>
        <p className="text-lg font-medium text-gray-700">Drop your CSV file here</p>
        <p className="text-sm text-gray-400 mt-1">or click to browse</p>
        <input ref={inputRef} type="file" accept=".csv" className="hidden"
          onChange={(e) => setFile(e.target.files[0])} />
      </div>

      {file && (
        <div className="flex items-center gap-3 bg-green-50 border border-green-200 rounded-lg p-4">
          <span className="text-green-600 text-xl">📄</span>
          <div className="flex-1">
            <p className="font-medium text-gray-800">{file.name}</p>
            <p className="text-sm text-gray-500">{(file.size / 1024).toFixed(1)} KB</p>
          </div>
          <button onClick={() => setFile(null)} className="text-gray-400 hover:text-red-500 text-xl">&times;</button>
        </div>
      )}

      {error && <p className="text-red-500 text-sm bg-red-50 border border-red-200 rounded p-3">{error}</p>}

      <button
        onClick={handleUpload}
        disabled={!file || loading}
        className="w-full py-3 bg-green-600 text-white rounded-lg font-semibold hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {loading ? "Uploading & Starting Pipeline..." : "Upload & Run Pipeline"}
      </button>

      <div>
        <h3 className="font-semibold text-gray-700 mb-2">Expected CSV Format:</h3>
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full text-xs">
            <thead className="bg-gray-50">
              <tr>
                {Object.keys(SAMPLE_ROWS[0]).map((k) => (
                  <th key={k} className="px-3 py-2 text-left font-medium text-gray-600">{k}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {SAMPLE_ROWS.map((row, i) => (
                <tr key={i} className="hover:bg-gray-50">
                  {Object.values(row).map((v, j) => (
                    <td key={j} className="px-3 py-2 text-gray-700">{v}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
