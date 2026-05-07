import React, { useEffect, useState, useRef } from "react";
import { createWebSocket, getPipelineStatus } from "../api/client";

const STEPS = [
  { key: "collector", label: "Data Collection", icon: "📥" },
  { key: "estimator", label: "Carbon Estimation", icon: "🧮" },
  { key: "verifier", label: "Verification", icon: "✅" },
  { key: "registry", label: "Blockchain Registry", icon: "⛓️" },
  { key: "complete", label: "Complete", icon: "🎉" },
];

const StatusBadge = ({ status }) => {
  const colors = {
    pending: "bg-gray-100 text-gray-600",
    running: "bg-blue-100 text-blue-700 animate-pulse",
    success: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
    warning: "bg-yellow-100 text-yellow-700",
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[status] || colors.pending}`}>
      {status}
    </span>
  );
};

function stepsFromResult(result) {
  if (!result) return {};
  const status = result.status;
  const out = {};

  if (result.validated_data) {
    out.collector = { status: "success", message: `Validated ${result.validated_data.length} rows` };
  }
  if (result.carbon_estimates) {
    const total = result.total_carbon_tons ?? 0;
    out.estimator = { status: "success", message: `Estimated ${total.toFixed(2)} tCO2 across ${result.carbon_estimates.length} sites` };
  }
  if (result.verification_result) {
    const v = result.verification_result;
    out.verifier = {
      status: v.overall_result === "PASS" ? "success" : "warning",
      message: `${v.passed_count ?? 0} passed, ${v.failed_count ?? 0} failed`,
    };
  }
  if (result.blockchain_result) {
    const b = result.blockchain_result;
    out.registry = { status: "success", message: `Registered ${b.registered_count ?? 0} credits on blockchain` };
  }
  if (status === "complete") {
    out.complete = { status: "success", message: `Pipeline complete! ${result.total_carbon_tons?.toFixed(2)} tCO2 registered.` };
  } else if (status === "failed") {
    const errStep = !result.carbon_estimates ? "collector"
      : !result.verification_result ? "estimator"
      : !result.blockchain_result ? "registry"
      : "complete";
    if (!out[errStep]) out[errStep] = { status: "failed", message: (result.errors || []).join(", ") || "Failed" };
  }
  return out;
}

export default function PipelineView({ runId }) {
  const [steps, setSteps] = useState({});
  const [finalResult, setFinalResult] = useState(null);
  const [connected, setConnected] = useState(false);
  const [pollStatus, setPollStatus] = useState("running");
  const doneRef = useRef(false);

  useEffect(() => {
    if (!runId) return;
    doneRef.current = false;
    setSteps({});
    setFinalResult(null);
    setPollStatus("running");

    // WebSocket for live updates
    const ws = createWebSocket(
      runId,
      (msg) => {
        if (msg.step === "heartbeat" || msg.step === "connected") {
          setConnected(true);
          return;
        }
        setSteps((prev) => ({
          ...prev,
          [msg.step]: { status: msg.status, message: msg.message, data: msg.data },
        }));
        if (msg.step === "complete" && msg.status === "success") {
          setFinalResult(msg.data);
          doneRef.current = true;
        }
      },
      () => setConnected(false)
    );

    // Polling fallback every 2.5s — fills in steps from DB when WS misses messages
    const poll = setInterval(async () => {
      if (doneRef.current) { clearInterval(poll); return; }
      try {
        const res = await getPipelineStatus(runId);
        const data = res.data;
        setPollStatus(data.status);
        if (data.status === "complete" || data.status === "failed") {
          const derived = stepsFromResult(data.result);
          setSteps((prev) => ({ ...derived, ...prev }));
          if (data.status === "complete" && data.result?.total_carbon_tons != null) {
            setFinalResult(data.result);
          }
          doneRef.current = true;
          clearInterval(poll);
        }
      } catch (_) {}
    }, 2500);

    return () => { ws.close(); clearInterval(poll); };
  }, [runId]);

  if (!runId) {
    return (
      <div className="text-center py-16 text-gray-400">
        <div className="text-5xl mb-4">🌊</div>
        <p>Upload a CSV file or draw on the map to start the pipeline.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${connected ? "bg-green-500" : "bg-yellow-400"}`} />
        <span className="text-sm text-gray-600">
          {connected ? "Live (WebSocket)" : "Polling for updates..."}
        </span>
        <span className="text-xs text-gray-400 ml-auto font-mono">Run: {runId?.slice(0, 8)}...</span>
      </div>

      <div className="space-y-3">
        {STEPS.map((step) => {
          const info = steps[step.key];
          const status = info?.status || "pending";
          return (
            <div key={step.key} className={`border rounded-xl p-4 transition-all ${
              status === "running" ? "border-blue-300 bg-blue-50" :
              status === "success" ? "border-green-300 bg-green-50" :
              status === "failed" ? "border-red-300 bg-red-50" :
              status === "warning" ? "border-yellow-300 bg-yellow-50" :
              "border-gray-200 bg-white"
            }`}>
              <div className="flex items-center gap-3">
                <span className="text-2xl">{step.icon}</span>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-gray-800">{step.label}</span>
                    <StatusBadge status={status} />
                  </div>
                  {info?.message && (
                    <p className="text-sm text-gray-600 mt-1">{info.message}</p>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {finalResult && (
        <div className="bg-green-600 text-white rounded-xl p-6">
          <h3 className="text-xl font-bold mb-2">Pipeline Complete!</h3>
          <p className="text-green-100 text-lg">
            Total Carbon Registered:{" "}
            <strong>{(finalResult.total_carbon_tons ?? finalResult.total_carbon_tons)?.toFixed(2)} tCO2</strong>
          </p>
          {(finalResult.blockchain_result?.blockchain_results ?? finalResult.blockchain_results ?? []).map((r, i) =>
            r.tx_hash ? (
              <p key={i} className="mt-2 text-green-200 text-sm font-mono truncate">
                TX: {r.tx_hash} {r.demo_mode ? "(demo)" : ""}
              </p>
            ) : null
          )}
        </div>
      )}

      {pollStatus === "failed" && !finalResult && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700 text-sm">
          Pipeline failed. Check the backend terminal for details.
        </div>
      )}
    </div>
  );
}
