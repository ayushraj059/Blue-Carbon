import React, { useState } from "react";
import UploadPanel from "./components/UploadPanel";
import PipelineView from "./components/PipelineView";
import RegistryTable from "./components/RegistryTable";
import OpsPanel from "./components/OpsPanel";
import MapPicker from "./components/MapPicker";

const TABS = [
  { id: "map", label: "Map Analysis", icon: "🗺️" },
  { id: "upload", label: "CSV Upload", icon: "📤" },
  { id: "pipeline", label: "Pipeline", icon: "⚙️" },
  { id: "registry", label: "Registry", icon: "📋" },
  { id: "ops", label: "Ops Monitor", icon: "📊" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("map");
  const [runId, setRunId] = useState(null);
  const [pipelineMsg, setPipelineMsg] = useState("");

  const handlePipelineStarted = (id, message) => {
    setRunId(id);
    setPipelineMsg(message || "Pipeline started.");
    setActiveTab("pipeline");
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 to-blue-50">
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center gap-3">
          <span className="text-3xl">🌊</span>
          <div>
            <h1 className="text-xl font-bold text-gray-900">Blue Carbon Registry</h1>
            <p className="text-xs text-gray-500">
              Satellite AI Analysis + Blockchain MRV — Polygon Network
            </p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            <span className="text-xs text-gray-500">Live</span>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex gap-1 bg-white rounded-xl p-1 border border-gray-200 mb-6 shadow-sm overflow-x-auto">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-shrink-0 flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? "bg-green-600 text-white shadow-sm"
                  : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
              {tab.id === "pipeline" && runId && (
                <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
              )}
            </button>
          ))}
        </div>

        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm min-h-96">
          {activeTab === "map" && (
            <div>
              <h2 className="text-lg font-bold text-gray-800 mb-1">
                Real-Time Satellite Analysis
              </h2>
              <p className="text-sm text-gray-500 mb-4">
                Draw a polygon on the satellite map or upload an aerial image → AI detects
                ecosystem type → carbon is calculated and registered on blockchain.
              </p>
              <MapPicker onPipelineStarted={handlePipelineStarted} />
            </div>
          )}
          {activeTab === "upload" && (
            <UploadPanel onUploadSuccess={(id) => handlePipelineStarted(id)} />
          )}
          {activeTab === "pipeline" && (
            <div>
              {pipelineMsg && (
                <div className="mb-4 bg-green-50 border border-green-200 rounded-lg p-3 text-green-800 text-sm">
                  {pipelineMsg}
                </div>
              )}
              <PipelineView runId={runId} />
            </div>
          )}
          {activeTab === "registry" && <RegistryTable />}
          {activeTab === "ops" && <OpsPanel />}
        </div>
      </main>
    </div>
  );
}
