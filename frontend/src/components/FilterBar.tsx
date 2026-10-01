import * as React from 'react';
import { Filter, RotateCcw } from 'lucide-react';
import { GraphFilterOptions } from './GraphCanvas';

interface FilterBarProps {
  filters: GraphFilterOptions;
  onChange: (filters: GraphFilterOptions) => void;
  onReset: () => void;
}

export const FilterBar: React.FC<FilterBarProps> = ({ filters, onChange, onReset }) => {
  const [isOpen, setIsOpen] = React.useState(false);

  const activeCount =
    (filters.minAmount > 0 ? 1 : 0) +
    (filters.paymentRail !== 'ALL' ? 1 : 0) +
    (filters.riskBand !== 'ALL' ? 1 : 0) +
    (filters.layer !== 'ALL' ? 1 : 0) +
    (filters.foreignIpOnly ? 1 : 0) +
    (filters.headlessOnly ? 1 : 0);

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition flex items-center gap-1.5 ${
          activeCount > 0
            ? 'bg-cyan-950/80 border-cyan-500/60 text-cyan-300'
            : 'bg-slate-900 border-slate-700 text-slate-300 hover:text-white'
        }`}
      >
        <Filter className="w-3.5 h-3.5" />
        <span>Filters</span>
        {activeCount > 0 && (
          <span className="px-1.5 py-0.2 bg-cyan-500 text-black text-[10px] font-bold rounded-full">
            {activeCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute top-full left-0 mt-2 w-80 bg-slate-900/95 backdrop-blur-md border border-slate-700 rounded-xl shadow-2xl p-4 z-40 space-y-3.5 text-xs text-slate-200">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <span className="font-semibold text-cyan-400 uppercase tracking-wider text-[11px]">
              Graph Display Filters
            </span>
            <button
              onClick={onReset}
              className="text-[11px] text-slate-400 hover:text-slate-200 flex items-center gap-1 font-mono"
            >
              <RotateCcw className="w-3 h-3" /> Reset
            </button>
          </div>

          {/* Min Amount Filter */}
          <div>
            <div className="flex justify-between text-slate-400 text-[11px] mb-1">
              <span>Min Transaction Amount</span>
              <span className="font-mono text-cyan-300 font-bold">
                ₹{filters.minAmount.toLocaleString()}
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={500000}
              step={5000}
              value={filters.minAmount}
              onChange={(e) => onChange({ ...filters, minAmount: Number(e.target.value) })}
              className="w-full accent-cyan-500 bg-slate-800 h-1.5 rounded"
            />
          </div>

          {/* Payment Rail */}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-slate-400 text-[11px] mb-1">Payment Rail</label>
              <select
                value={filters.paymentRail}
                onChange={(e) => onChange({ ...filters, paymentRail: e.target.value })}
                className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-slate-200"
              >
                <option value="ALL">All Rails</option>
                <option value="UPI">UPI</option>
                <option value="IMPS">IMPS</option>
                <option value="NEFT">NEFT</option>
                <option value="RTGS">RTGS</option>
              </select>
            </div>

            {/* Mule Risk Band */}
            <div>
              <label className="block text-slate-400 text-[11px] mb-1">Mule Risk Band</label>
              <select
                value={filters.riskBand}
                onChange={(e) => onChange({ ...filters, riskBand: e.target.value })}
                className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-slate-200"
              >
                <option value="ALL">All Bands</option>
                <option value="CRITICAL">Critical (&gt;=70)</option>
                <option value="HIGH">High (40-69)</option>
                <option value="NORMAL">Normal (&lt;40)</option>
              </select>
            </div>
          </div>

          {/* Layer Filter */}
          <div>
            <label className="block text-slate-400 text-[11px] mb-1">Account Layer</label>
            <div className="grid grid-cols-5 gap-1 bg-slate-950 p-1 rounded border border-slate-800 font-mono text-[10px] text-center">
              {['ALL', 'Victim', 'L1', 'L2', 'L3'].map((l) => (
                <button
                  key={l}
                  onClick={() => onChange({ ...filters, layer: l })}
                  className={`py-1 rounded transition ${
                    filters.layer === l ? 'bg-cyan-600 text-white font-bold' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {l}
                </button>
              ))}
            </div>
          </div>

          {/* Checkboxes for Foreign IP & Headless Device */}
          <div className="space-y-1.5 pt-1 border-t border-slate-800 text-[11px]">
            <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={filters.foreignIpOnly}
                onChange={(e) => onChange({ ...filters, foreignIpOnly: e.target.checked })}
                className="rounded border-slate-700 bg-slate-950 text-cyan-500 focus:ring-0"
              />
              <span>Foreign IP Anonymizers Only</span>
            </label>

            <label className="flex items-center gap-2 text-slate-300 cursor-pointer">
              <input
                type="checkbox"
                checked={filters.headlessOnly}
                onChange={(e) => onChange({ ...filters, headlessOnly: e.target.checked })}
                className="rounded border-slate-700 bg-slate-950 text-cyan-500 focus:ring-0"
              />
              <span>Headless Automated Devices Only</span>
            </label>
          </div>
        </div>
      )}
    </div>
  );
};
