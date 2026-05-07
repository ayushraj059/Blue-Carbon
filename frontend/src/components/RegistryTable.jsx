import React, { useEffect, useState } from "react";
import { getCredits } from "../api/client";

const StatusBadge = ({ status }) => {
  const colors = {
    VERIFIED: "bg-green-100 text-green-700",
    PENDING: "bg-yellow-100 text-yellow-700",
    FAILED: "bg-red-100 text-red-700",
  };
  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${colors[status] || "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  );
};

const TxHash = ({ hash }) => {
  const [copied, setCopied] = useState(false);
  if (!hash) return <span className="text-gray-400 text-sm">—</span>;

  const short = `${hash.slice(0, 8)}...${hash.slice(-6)}`;

  const copy = () => {
    navigator.clipboard.writeText(hash);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="flex items-center gap-1">
      <a href={`https://mumbai.polygonscan.com/tx/${hash}`} target="_blank" rel="noreferrer"
        className="text-blue-600 hover:underline font-mono text-xs">{short}</a>
      <button onClick={copy} className="text-gray-400 hover:text-gray-700 text-xs ml-1">
        {copied ? "✓" : "⎘"}
      </button>
    </div>
  );
};

export default function RegistryTable() {
  const [credits, setCredits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const limit = 10;

  const load = async () => {
    setLoading(true);
    try {
      const res = await getCredits(limit, offset);
      setCredits(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [offset]);

  if (loading) return (
    <div className="text-center py-16">
      <div className="animate-spin text-4xl">🌀</div>
      <p className="text-gray-500 mt-2">Loading registry...</p>
    </div>
  );

  if (credits.length === 0) return (
    <div className="text-center py-16 text-gray-400">
      <div className="text-5xl mb-4">📋</div>
      <p>No carbon credits registered yet.</p>
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="font-semibold text-gray-700">{credits.length} credits loaded</h3>
        <button onClick={load} className="text-sm text-green-600 hover:underline">Refresh</button>
      </div>

      <div className="overflow-x-auto rounded-xl border border-gray-200">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-gray-600 text-xs uppercase">
            <tr>
              {["Project ID", "Site ID", "Carbon Tons", "Status", "Blockchain TX", "Registered At"].map(h => (
                <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {credits.map((c) => (
              <tr key={c.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-mono text-xs text-gray-700">{c.project_id}</td>
                <td className="px-4 py-3 text-gray-700">{c.site_id}</td>
                <td className="px-4 py-3 font-semibold text-green-700">{c.carbon_tons?.toFixed(2)}</td>
                <td className="px-4 py-3"><StatusBadge status={c.verification_status} /></td>
                <td className="px-4 py-3"><TxHash hash={c.blockchain_tx_hash} /></td>
                <td className="px-4 py-3 text-gray-500 text-xs">{new Date(c.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex gap-2 justify-center">
        <button onClick={() => setOffset(Math.max(0, offset - limit))} disabled={offset === 0}
          className="px-4 py-2 text-sm border rounded-lg disabled:opacity-40 hover:bg-gray-50">
          Previous
        </button>
        <button onClick={() => setOffset(offset + limit)} disabled={credits.length < limit}
          className="px-4 py-2 text-sm border rounded-lg disabled:opacity-40 hover:bg-gray-50">
          Next
        </button>
      </div>
    </div>
  );
}
