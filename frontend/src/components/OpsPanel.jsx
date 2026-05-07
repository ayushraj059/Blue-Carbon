import React, { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { getOpsMetrics } from "../api/client";

const MetricCard = ({ label, value, unit, color }) => (
  <div className={`rounded-xl p-5 border ${color}`}>
    <p className="text-sm text-gray-500 font-medium">{label}</p>
    <p className="text-3xl font-bold mt-1 text-gray-800">{value}<span className="text-base font-normal text-gray-500 ml-1">{unit}</span></p>
  </div>
);

const COLORS = ["#22c55e", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6"];

export default function OpsPanel() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const res = await getOpsMetrics();
      setMetrics(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return (
    <div className="text-center py-16">
      <div className="animate-spin text-4xl">🌀</div>
      <p className="text-gray-500 mt-2">Loading metrics...</p>
    </div>
  );

  if (!metrics) return <p className="text-gray-500 text-center py-8">No metrics available.</p>;

  const latencyData = Object.entries(metrics.agent_latencies || {}).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    latency: value,
  }));

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Total Runs" value={metrics.total_runs} unit="runs" color="border-green-200 bg-green-50" />
        <MetricCard label="Success Rate" value={metrics.success_rate} unit="%" color="border-blue-200 bg-blue-50" />
        <MetricCard label="Avg Duration" value={metrics.avg_pipeline_duration_seconds} unit="sec" color="border-yellow-200 bg-yellow-50" />
        <MetricCard label="Uptime" value={metrics.uptime_percentage} unit="%" color="border-purple-200 bg-purple-50" />
      </div>

      <div className="border rounded-xl p-5">
        <h3 className="font-semibold text-gray-700 mb-4">Agent Latency (avg seconds)</h3>
        {latencyData.length > 0 ? (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={latencyData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v) => [`${v.toFixed(2)}s`, "Avg Latency"]} />
              <Bar dataKey="latency" radius={[4, 4, 0, 0]}>
                {latencyData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-gray-400 text-center py-8">Run a pipeline to see agent latencies.</p>
        )}
      </div>

      <div className="text-xs text-gray-400 text-right">
        Last updated: {metrics.last_updated ? new Date(metrics.last_updated).toLocaleTimeString() : "—"}
      </div>
    </div>
  );
}
