import * as React from 'react';
import { useEffect, useRef, useState, useImperativeHandle, forwardRef } from 'react';
import cytoscape, { Core } from 'cytoscape';
import { TraceNode, TraceResult } from '../api';
import { Layers, Network, RefreshCw } from 'lucide-react';

export interface GraphFilterOptions {
  minAmount: number;
  paymentRail: string;
  riskBand: string;
  layer: string;
  foreignIpOnly: boolean;
  headlessOnly: boolean;
}

interface GraphCanvasProps {
  traceResult: TraceResult | null;
  selectedNode: TraceNode | null;
  onNodeClick: (node: TraceNode | null) => void;
  useForceLayout?: boolean;
  maxTimeEpoch?: number;
  filters?: GraphFilterOptions;
}

export interface GraphCanvasRef {
  resetView: () => void;
}

const defaultFilters: GraphFilterOptions = {
  minAmount: 0,
  paymentRail: 'ALL',
  riskBand: 'ALL',
  layer: 'ALL',
  foreignIpOnly: false,
  headlessOnly: false,
};

export const GraphCanvas = forwardRef<GraphCanvasRef, GraphCanvasProps>(({
  traceResult,
  selectedNode,
  onNodeClick,
  useForceLayout = false,
  maxTimeEpoch = Infinity,
  filters = defaultFilters,
}, ref) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const prevVisibleEdgeIdsRef = useRef<Set<string>>(new Set());

  const [layoutType, setLayoutType] = useState<'layered' | 'force'>(
    useForceLayout ? 'force' : 'layered'
  );
  const [tooltip, setTooltip] = useState<{ x: number; y: number; content: string } | null>(null);

  useImperativeHandle(ref, () => ({
    resetView: () => {
      cyRef.current?.fit(undefined, 50);
    },
  }));

  useEffect(() => {
    setLayoutType(useForceLayout ? 'force' : 'layered');
  }, [useForceLayout]);

  // Initial Graph Setup when traceResult or layoutType changes
  useEffect(() => {
    if (!containerRef.current) return;

    if (!traceResult || !traceResult.nodes || traceResult.nodes.length === 0) {
      if (cyRef.current) {
        cyRef.current.destroy();
        cyRef.current = null;
      }
      return;
    }

    const nodes = traceResult.nodes;
    const edges = traceResult.edges || [];

    const elements: cytoscape.ElementDefinition[] = [];

    // Map Nodes
    nodes.forEach((n) => {
      const isVictim = n.hop === 0 || n.layer === 'Victim';
      let color = '#00f0ff'; // Victim cyan
      if (n.layer === 'L1') color = '#f59e0b'; // Amber
      else if (n.layer === 'L2') color = '#ef4444'; // Red
      else if (n.layer === 'L3') color = '#a855f7'; // Purple

      const isHolding = n.residual_balance > 0 && !isVictim;
      const size = Math.max(35, Math.min(75, 30 + Math.sqrt(n.amount_received || 1000) / 20));

      // Calculate position for Layered DAG layout
      const layerX = n.hop * 260;
      const sameHopNodes = nodes.filter((x) => x.hop === n.hop);
      const nodeIndex = sameHopNodes.findIndex((x) => x.account === n.account);
      const layerY = (nodeIndex - sameHopNodes.length / 2) * 110;

      elements.push({
        group: 'nodes',
        data: {
          id: n.account,
          label: `${n.account.slice(-4)} (${n.layer})`,
          account: n.account,
          layer: n.layer,
          risk_score: n.mule_risk_score,
          color: color,
          borderColor: isHolding ? '#10b981' : color,
          borderWidth: isHolding ? 4 : 2,
          size: size,
          rawNode: n,
        },
        position: { x: layerX, y: layerY },
      });
    });

    // Map Edges
    edges.forEach((e) => {
      const width = Math.max(1.5, Math.min(8, Math.sqrt(e.amount) / 50));
      elements.push({
        group: 'edges',
        data: {
          id: `${e.sender_account}_${e.receiver_account}_${e.txn_id}`,
          source: e.sender_account,
          target: e.receiver_account,
          label: `₹${(e.amount / 1000).toFixed(1)}k`,
          amount: e.amount,
          epoch_sec: e.epoch_sec,
          payment_mode: e.payment_mode,
          width: width,
          txn_id: e.txn_id,
          timestamp: e.timestamp,
        },
      });
    });

    // Initialize Cytoscape Instance
    const cy = cytoscape({
      container: containerRef.current,
      elements: elements,
      boxSelectionEnabled: false,
      autounselectify: false,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': 'data(color)',
            'border-color': 'data(borderColor)',
            'border-width': 'data(borderWidth)',
            width: 'data(size)',
            height: 'data(size)',
            label: 'data(label)',
            color: '#f8fafc',
            'font-size': '11px',
            'font-family': 'Inter, sans-serif',
            'font-weight': 'bold',
            'text-valign': 'bottom',
            'text-margin-y': 6,
            'text-background-opacity': 0.8,
            'text-background-color': '#070b14',
            'text-background-padding': '3px',
            'text-background-shape': 'roundrectangle',
          },
        },
        {
          selector: 'node:selected',
          style: {
            'border-color': '#ffffff',
            'border-width': 5,
            'shadow-blur': 15,
            'shadow-color': '#00f0ff',
            'shadow-opacity': 0.9,
          } as any,
        },
        {
          selector: 'edge',
          style: {
            width: 'data(width)',
            'line-color': '#334155',
            'target-arrow-color': '#38bdf8',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            opacity: 0.8,
          },
        },
        {
          selector: 'edge.edge-pulse',
          style: {
            'line-color': '#00f0ff',
            'target-arrow-color': '#00f0ff',
            opacity: 1,
            width: 5,
          },
        },
        {
          selector: 'edge:hover',
          style: {
            'line-color': '#00f0ff',
            'target-arrow-color': '#00f0ff',
            opacity: 1,
            width: 4,
          },
        },
      ],
    });

    if (layoutType === 'force') {
      cy.layout({ name: 'cose', animate: true, refresh: 20 }).run();
    } else {
      cy.layout({ name: 'preset' }).run();
    }

    cy.fit(undefined, 50);

    // Event Handlers
    cy.on('tap', 'node', (evt: cytoscape.EventObject) => {
      const nodeData = evt.target.data('rawNode');
      onNodeClick(nodeData);
    });

    cy.on('tap', (evt: cytoscape.EventObject) => {
      if (evt.target === cy) {
        onNodeClick(null);
      }
    });

    cy.on('mouseover', 'edge', (evt: cytoscape.EventObject) => {
      const e = evt.target.data();
      const pos = evt.renderedPosition;
      setTooltip({
        x: pos.x,
        y: pos.y,
        content: `TXN: ${e.txn_id} | Amount: ₹${e.amount.toLocaleString()} | Mode: ${e.payment_mode} | ${e.timestamp}`,
      });
    });

    cy.on('mouseout', 'edge', () => {
      setTooltip(null);
    });

    cyRef.current = cy;
    prevVisibleEdgeIdsRef.current = new Set();

    return () => {
      cy.destroy();
    };
  }, [traceResult, layoutType, onNodeClick]);

  // Dynamic Visibility Updates using cy.batch() (no graph reconstruction)
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    const newlyActiveEdgeIds: string[] = [];
    const currentVisibleEdgeIds = new Set<string>();

    cy.batch(() => {
      // 1. Filter & update edges
      cy.edges().forEach((edge) => {
        const amt = edge.data('amount') || 0;
        const mode = edge.data('payment_mode') || 'UPI';
        const epochSec = edge.data('epoch_sec') || 0;

        const passesMinAmount = amt >= filters.minAmount;
        const passesRail = filters.paymentRail === 'ALL' || mode === filters.paymentRail;
        const passesTime = maxTimeEpoch === Infinity || epochSec <= maxTimeEpoch;

        const isVisible = passesMinAmount && passesRail && passesTime;

        if (isVisible) {
          edge.style('display', 'element');
          currentVisibleEdgeIds.add(edge.id());

          if (!prevVisibleEdgeIdsRef.current.has(edge.id())) {
            newlyActiveEdgeIds.push(edge.id());
          }
        } else {
          edge.style('display', 'none');
        }
      });

      // 2. Filter & update nodes
      cy.nodes().forEach((node) => {
        const raw = node.data('rawNode') as TraceNode;
        const isVictim = raw.hop === 0 || raw.layer === 'Victim';

        // Layer Filter
        const passesLayer = filters.layer === 'ALL' || raw.layer === filters.layer;

        // Risk Band Filter
        let passesRisk = true;
        if (filters.riskBand === 'CRITICAL') passesRisk = raw.mule_risk_score >= 70;
        else if (filters.riskBand === 'HIGH') passesRisk = raw.mule_risk_score >= 40 && raw.mule_risk_score < 70;
        else if (filters.riskBand === 'NORMAL') passesRisk = raw.mule_risk_score < 40;

        // Connected to visible edge or victim node
        const connectedEdges = node.connectedEdges();
        const hasVisibleEdge = connectedEdges.some((e: any) => currentVisibleEdgeIds.has(e.id()));

        const isVisible = passesLayer && passesRisk && (isVictim || hasVisibleEdge);

        if (isVisible) {
          node.style('display', 'element');
        } else {
          node.style('display', 'none');
        }
      });
    });

    // Apply pulse animation to newly active edges
    if (newlyActiveEdgeIds.length > 0) {
      newlyActiveEdgeIds.forEach((id) => {
        const ele = cy.getElementById(id);
        if (ele && ele.length) ele.addClass('edge-pulse');
      });

      setTimeout(() => {
        if (!cy.destroyed()) {
          cy.batch(() => {
            newlyActiveEdgeIds.forEach((id) => {
              const ele = cy.getElementById(id);
              if (ele && ele.length) ele.removeClass('edge-pulse');
            });
          });
        }
      }, 600);
    }

    prevVisibleEdgeIdsRef.current = currentVisibleEdgeIds;
  }, [maxTimeEpoch, filters]);

  // Handle selectedNode highlighting
  useEffect(() => {
    if (cyRef.current && selectedNode) {
      cyRef.current.nodes().unselect();
      const target = cyRef.current.nodes(`[id = "${selectedNode.account}"]`);
      if (target.length > 0) {
        target.select();
      }
    }
  }, [selectedNode]);

  return (
    <div className="relative w-full h-full bg-[#070b14] overflow-hidden flex flex-col">
      {/* Top Overlay Controls */}
      <div className="absolute top-4 left-4 z-10 flex items-center gap-2 bg-[#0f172a]/90 backdrop-blur p-1.5 rounded-xl border border-slate-800 shadow-xl">
        <button
          onClick={() => setLayoutType('layered')}
          className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition flex items-center gap-1.5 ${
            layoutType === 'layered'
              ? 'bg-cyan-500 text-black shadow-lg shadow-cyan-500/20'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          Layered DAG
        </button>
        <button
          onClick={() => setLayoutType('force')}
          className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition flex items-center gap-1.5 ${
            layoutType === 'force'
              ? 'bg-cyan-500 text-black shadow-lg shadow-cyan-500/20'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Network className="w-3.5 h-3.5" />
          Force Directed
        </button>
        <div className="w-px h-4 bg-slate-800 my-auto" />
        <button
          onClick={() => cyRef.current?.fit(undefined, 50)}
          className="p-1.5 text-slate-400 hover:text-cyan-400 rounded-lg transition"
          title="Reset View"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Bottom Legend */}
      <div className="absolute bottom-4 left-4 z-10 bg-[#0f172a]/90 backdrop-blur p-3 rounded-xl border border-slate-800/80 text-xs flex items-center gap-4 text-slate-300 shadow-xl">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full bg-[#00f0ff]" />
          <span>Victim</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full bg-[#f59e0b]" />
          <span>L1 Collector</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full bg-[#ef4444]" />
          <span>L2 Distributor</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full bg-[#a855f7]" />
          <span>L3 Terminal</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full border-2 border-emerald-400 bg-transparent" />
          <span className="text-emerald-300 font-semibold">Freeze Account</span>
        </div>
      </div>

      {/* Edge Hover Tooltip */}
      {tooltip && (
        <div
          style={{ left: tooltip.x + 10, top: tooltip.y + 10 }}
          className="absolute z-30 pointer-events-none bg-slate-900 border border-cyan-500/60 px-3 py-1.5 rounded-lg text-xs font-mono text-cyan-200 shadow-xl"
        >
          {tooltip.content}
        </div>
      )}

      {/* Cytoscape Canvas Container */}
      <div ref={containerRef} className="w-full h-full cursor-grab active:cursor-grabbing" />
    </div>
  );
});

GraphCanvas.displayName = 'GraphCanvas';
