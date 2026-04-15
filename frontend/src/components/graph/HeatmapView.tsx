import { useEffect, useState, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { AlertTriangle, TrendingUp, Users, Shield, Filter, ArrowUpDown, ChevronDown, ChevronUp, Search, Download, Eye } from "lucide-react";
import type { ExpertiseMatrixData } from "../../types";

/* ── Types ── */
type SortBy ="name" | "total" | "topics";
type SortDir ="asc" | "desc";

/* ── Dark mode hook ── */
function useIsDark() {
 const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
 useEffect(() => {
 const obs = new MutationObserver(() => setDark(document.documentElement.classList.contains("dark")));
 obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
 return () => obs.disconnect();
 }, []);
 return dark;
}

/* ── Heat color — dark mode aware ── */
function getHeatColor(score: number, isDark: boolean): string {
 if (score === 0) return isDark ? "rgba(30, 41, 59, 0.5)" : "rgba(248, 250, 252, 1)";
 if (isDark) {
 // Dark mode: deeper, more saturated colors
 if (score <= 0.15) return `rgba(99, 102, 241, 0.2)`;
 if (score <= 0.3) return `rgba(99, 102, 241, 0.35)`;
 if (score <= 0.5) return `rgba(99, 102, 241, 0.5)`;
 if (score <= 0.7) return `rgba(124, 58, 237, 0.6)`;
 if (score <= 0.85) return `rgba(139, 92, 246, 0.75)`;
 return `rgba(147, 51, 234, 0.9)`;
 }
 // Light mode
 if (score <= 0.15) return `rgba(224, 231, 255, ${0.5 + score * 3})`;
 if (score <= 0.3) return `rgba(165, 180, 252, ${0.6 + score})`;
 if (score <= 0.5) return `rgba(129, 140, 248, ${0.7 + score * 0.4})`;
 if (score <= 0.7) return `rgba(99, 102, 241, ${0.8 + score * 0.2})`;
 if (score <= 0.85) return `rgba(124, 58, 237, ${0.85 + score * 0.1})`;
 return `rgba(126, 34, 206, 0.95)`;
}

function getTextColor(score: number, isDark: boolean): string {
 if (score === 0) return isDark ? "#475569" : "#cbd5e1";
 return score > 0.35 ? "#ffffff" : isDark ? "#e2e8f0" : "#475569";
}

function getInitials(name: string): string {
 return name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();
}

function getAvatarColor(name: string): string {
 const colors = ["#6366f1", "#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#ec4899", "#14b8a6"];
 let hash = 0;
 for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
 return colors[Math.abs(hash) % colors.length];
}

/* ── Sparkline component ── */
function Sparkline({ values, width = 60, height = 20 }: { values: number[]; width?: number; height?: number }) {
 if (values.length === 0) return null;
 const max = Math.max(...values, 0.01);
 const points = values.map((v, i) => {
 const x = (i / Math.max(values.length - 1, 1)) * width;
 const y = height - (v / max) * height;
 return `${x},${y}`;
 }).join("");

 return (
 <svg width={width} height={height} className="inline-block">
 <polyline points={points} fill="none" stroke="#818cf8" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
 {values.length > 0 && (
 <circle cx={(values.length - 1) / Math.max(values.length - 1, 1) * width} cy={height - (values[values.length - 1] / max) * height} r={2} fill="#6366f1" />
 )}
 </svg>
 );
}

/* ── Main Component ── */
export interface HeatmapViewProps {
 className?: string;
}

export default function HeatmapView(_props?: HeatmapViewProps) {
 const navigate = useNavigate();
 const isDark = useIsDark();
 const [data, setData] = useState<ExpertiseMatrixData | null>(null);
 const [isLoading, setIsLoading] = useState(true);
 const [hoveredCell, setHoveredCell] = useState<{ member: string; topic: string } | null>(null);
 const [hoveredRow, setHoveredRow] = useState<string | null>(null);
 const [hoveredCol, setHoveredCol] = useState<string | null>(null);
 const [sortBy, setSortBy] = useState<SortBy>("total");
 const [sortDir, setSortDir] = useState<SortDir>("desc");
 const [sortByTopic, setSortByTopic] = useState<string | null>(null);
 const [searchTerm, setSearchTerm] = useState("");
 const [hiddenTopics, setHiddenTopics] = useState<Set<string>>(new Set());
 const [showFilterPanel, setShowFilterPanel] = useState(false);
 const [showGaps, setShowGaps] = useState(true);

 // BUG-010: [] is intentional — no props/context affect the matrix fetch; load once on mount
 useEffect(() => {
 api.getExpertiseMatrix().then(setData).catch(() => setData(null)).finally(() => setIsLoading(false));
 }, []);

 // Toggle sort direction
 const handleSort = useCallback((newSort: SortBy) => {
 if (sortBy === newSort) {
 setSortDir((d) => d ==="desc" ? "asc" : "desc");
 } else {
 setSortBy(newSort);
 setSortByTopic(null);
 setSortDir("desc");
 }
 }, [sortBy]);

 // Sort by topic column
 const handleTopicSort = useCallback((topic: string) => {
 if (sortByTopic === topic) {
 setSortDir((d) => d ==="desc" ? "asc" : "desc");
 } else {
 setSortByTopic(topic);
 setSortBy("total"); // reset generic sort
 setSortDir("desc");
 }
 }, [sortByTopic]);

 // Toggle topic visibility
 const toggleTopic = useCallback((topic: string) => {
 setHiddenTopics((prev) => {
 const next = new Set(prev);
 if (next.has(topic)) next.delete(topic);
 else next.add(topic);
 return next;
 });
 }, []);

 // Export as CSV
 const exportCSV = useCallback(() => {
 if (!data) return;
 const topics = data.topics.filter((t) => !hiddenTopics.has(t));
 const header = ["Member", ...topics, "Total"].join(",");
 const rows = data.members.map((m) => {
 const scores = topics.map((t) => Math.round((m.scores[t] || 0) * 100));
 const total = scores.reduce((a, b) => a + b, 0);
 return [m.name, ...scores, total].join(",");
 });
 const csv = [header, ...rows].join("\n");
 const blob = new Blob([csv], { type: "text/csv" });
 const url = URL.createObjectURL(blob);
 const a = document.createElement("a");
 a.href = url;
 a.download ="expertise-matrix.csv";
 a.click();
 URL.revokeObjectURL(url);
 }, [data, hiddenTopics]);

 // Computed data
 const { sortedMembers, activeTopics, memberTotals, topicAverages, busFactor, gapTopics, strongTopics } = useMemo(() => {
 if (!data) return { sortedMembers: [] as ExpertiseMatrixData["members"], activeTopics: [] as string[], memberTotals: new Map<string, number>(), topicAverages: new Map<string, number>(), busFactor: [] as { topic: string; expert: string }[], gapTopics: [] as string[], strongTopics: [] as string[] };

 // Filter active topics (topics with at least one score > 0)
 const active = data.topics.filter((t) => !hiddenTopics.has(t) && data.members.some((m) => (m.scores[t] || 0) > 0));

 // Sort topics by number of members who have the skill
 const topicMemberCount = new Map<string, number>();
 for (const t of active) {
 topicMemberCount.set(t, data.members.filter((m) => (m.scores[t] || 0) > 0).length);
 }
 const sortedTopics = [...active].sort((a, b) => (topicMemberCount.get(b) || 0) - (topicMemberCount.get(a) || 0));

 // Compute member totals and topic counts
 const totals = new Map<string, number>();
 const topicCounts = new Map<string, number>();
 for (const m of data.members) {
 const total = sortedTopics.reduce((sum, t) => sum + (m.scores[t] || 0), 0);
 const count = sortedTopics.filter((t) => (m.scores[t] || 0) > 0).length;
 totals.set(m.id, total);
 topicCounts.set(m.id, count);
 }

 // Compute topic averages
 const avgMap = new Map<string, number>();
 for (const t of sortedTopics) {
 const scores = data.members.map((m) => m.scores[t] || 0).filter((s) => s > 0);
 avgMap.set(t, scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : 0);
 }

 // Bus factor: topics with only 1 expert (score > 0.5)
 const bus: { topic: string; expert: string }[] = [];
 const gaps: string[] = [];
 const strong: string[] = [];
 for (const t of sortedTopics) {
 const experts = data.members.filter((m) => (m.scores[t] || 0) > 0.5);
 const knowers = data.members.filter((m) => (m.scores[t] || 0) > 0);
 if (experts.length === 1) {
 bus.push({ topic: t, expert: experts[0].name });
 }
 if (knowers.length <= 1) {
 gaps.push(t);
 }
 if (experts.length >= 3) {
 strong.push(t);
 }
 }

 // Filter by search
 let members = data.members;
 if (searchTerm.trim()) {
 const term = searchTerm.toLowerCase();
 members = members.filter((m) => m.name.toLowerCase().includes(term));
 }

 // Sort members
 const sorted = [...members].sort((a, b) => {
 let cmp = 0;
 if (sortByTopic) {
 cmp = (a.scores[sortByTopic] || 0) - (b.scores[sortByTopic] || 0);
 } else if (sortBy ==="name") {
 cmp = a.name.localeCompare(b.name);
 } else if (sortBy ==="total") {
 cmp = (totals.get(a.id) || 0) - (totals.get(b.id) || 0);
 } else {
 cmp = (topicCounts.get(a.id) || 0) - (topicCounts.get(b.id) || 0);
 }
 return sortDir ==="desc" ? -cmp : cmp;
 });

 return { sortedMembers: sorted, activeTopics: sortedTopics, memberTotals: totals, topicAverages: avgMap, busFactor: bus, gapTopics: gaps, strongTopics: strong };
 }, [data, sortBy, sortDir, sortByTopic, searchTerm, hiddenTopics]);

 if (isLoading) {
 return (
 <div className="flex items-center justify-center h-full">
 <div className="text-center">
 <div className="w-10 h-10 border-3 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto" />
 <p className="text-sm text-slate-500 mt-3">Loading expertise matrix...</p>
 </div>
 </div>
 );
 }

 if (!data || data.members.length === 0 || activeTopics.length === 0) {
 return (
 <div className="text-center py-16">
 <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-500 mb-4">
 <span className="text-2xl">📊</span>
 </div>
 <h3 className="text-lg font-semibold text-slate-700">No expertise data</h3>
 <p className="text-sm text-slate-500 mt-1">Add members with expertise tags or ingest contributions.</p>
 </div>
 );
 }

 return (
 <div className="p-4 sm:p-6 h-full overflow-auto">
 {/* ── Header ── */}
 <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-4 gap-3">
 <div>
 <h3 className="text-base font-bold text-slate-800">Expertise Matrix</h3>
 <p className="text-xs text-slate-500 mt-0.5">
 Who knows what — {sortedMembers.length} members × {activeTopics.length} topics
 </p>
 </div>
 <div className="flex items-center gap-2 flex-wrap">
 {/* Search */}
 <div className="relative">
 <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
 <input
 value={searchTerm}
 onChange={(e) => setSearchTerm(e.target.value)}
 placeholder="Filter members..." className="pl-7 pr-3 py-1.5 w-40 text-xs bg-elevated border border-default rounded-lg text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/30" />
 </div>

 {/* Sort buttons */}
 <div className="flex items-center gap-1">
 <span className="text-2xs font-semibold text-slate-400 uppercase">Sort:</span>
 {(["total", "topics", "name"] as SortBy[]).map((s) => (
 <button
 key={s}
 onClick={() => handleSort(s)}
 className={`px-2.5 py-1 text-[11px] font-medium rounded-md transition-all flex items-center gap-0.5 ${
 sortBy === s && !sortByTopic
 ? "bg-indigo-100 text-indigo-700" : "text-slate-500" }`}
 >
 {s ==="total" ? "Expertise" : s ==="topics" ? "Breadth" : "Name"}
 {sortBy === s && !sortByTopic && (sortDir ==="desc" ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />)}
 </button>
 ))}
 </div>

 {/* Filter */}
 <button
 onClick={() => setShowFilterPanel(!showFilterPanel)}
 className={`p-1.5 rounded-lg border transition-colors ${showFilterPanel ? "bg-indigo-50 border-indigo-200 text-indigo-600" : "border-default text-slate-500"}`}
 title="Filter topics" >
 <Filter className="w-3.5 h-3.5" />
 </button>

 {/* Export */}
 <button
 onClick={exportCSV}
 className="p-1.5 rounded-lg border border-default text-slate-500 transition-colors" title="Export CSV" >
 <Download className="w-3.5 h-3.5" />
 </button>

 {/* Toggle gaps */}
 <button
 onClick={() => setShowGaps(!showGaps)}
 className={`p-1.5 rounded-lg border transition-colors ${showGaps ? "bg-amber-50 border-amber-200 text-amber-600" : "border-default text-slate-500"}`}
 title={showGaps ? "Hide gap analysis" : "Show gap analysis"}
 >
 <Eye className="w-3.5 h-3.5" />
 </button>
 </div>
 </div>

 {/* ── Filter panel ── */}
 {showFilterPanel && (
 <div className="mb-4 p-3 bg-elevated border border-default rounded-xl shadow-sm">
 <div className="flex items-center justify-between mb-2">
 <p className="text-xs font-bold text-slate-600">Filter Topics</p>
 <div className="flex gap-2">
 <button onClick={() => setHiddenTopics(new Set())} className="text-2xs text-indigo-600 hover:underline">Show All</button>
 <button onClick={() => setHiddenTopics(new Set(data?.topics || []))} className="text-2xs text-slate-500 hover:underline">Hide All</button>
 </div>
 </div>
 <div className="flex flex-wrap gap-1.5">
 {(data?.topics || []).filter((t) => data!.members.some((m) => (m.scores[t] || 0) > 0)).map((topic) => (
 <button
 key={topic}
 onClick={() => toggleTopic(topic)}
 className={`px-2 py-1 text-2xs font-medium rounded-md transition-all ${
 hiddenTopics.has(topic)
 ? "bg-muted text-slate-400 line-through" : "bg-indigo-50 text-indigo-600" }`}
 >
 {topic}
 </button>
 ))}
 </div>
 </div>
 )}

 {/* ── Gap Analysis Cards ── */}
 {showGaps && (busFactor.length > 0 || gapTopics.length > 0 || strongTopics.length > 0) && (
 <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">
 {/* Bus Factor Risks */}
 {busFactor.length > 0 && (
 <div className="p-3 bg-red-50 border border-red-200 rounded-xl">
 <div className="flex items-center gap-1.5 mb-2">
 <AlertTriangle className="w-3.5 h-3.5 text-red-500" />
 <span className="text-xs font-bold text-red-700">Bus Factor Risks</span>
 <span className="ml-auto text-2xs font-mono font-bold text-red-500 bg-red-100 px-1.5 py-0.5 rounded">{busFactor.length}</span>
 </div>
 <div className="space-y-1 max-h-20 overflow-y-auto">
 {busFactor.slice(0, 5).map((bf) => (
 <div key={bf.topic} className="flex items-center justify-between text-2xs">
 <span className="text-red-600 truncate">{bf.topic}</span>
 <span className="text-red-500 font-medium shrink-0 ml-2">→ {bf.expert}</span>
 </div>
 ))}
 {busFactor.length > 5 && <p className="text-2xs text-red-400 italic">+{busFactor.length - 5} more</p>}
 </div>
 </div>
 )}

 {/* Knowledge Gaps */}
 {gapTopics.length > 0 && (
 <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl">
 <div className="flex items-center gap-1.5 mb-2">
 <Shield className="w-3.5 h-3.5 text-amber-500" />
 <span className="text-xs font-bold text-amber-700">Knowledge Gaps</span>
 <span className="ml-auto text-2xs font-mono font-bold text-amber-500 bg-amber-100 px-1.5 py-0.5 rounded">{gapTopics.length}</span>
 </div>
 <div className="flex flex-wrap gap-1 max-h-20 overflow-y-auto">
 {gapTopics.slice(0, 8).map((t) => (
 <span key={t} className="text-2xs bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded">{t}</span>
 ))}
 {gapTopics.length > 8 && <span className="text-2xs text-amber-400 italic">+{gapTopics.length - 8} more</span>}
 </div>
 </div>
 )}

 {/* Well Covered */}
 {strongTopics.length > 0 && (
 <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl">
 <div className="flex items-center gap-1.5 mb-2">
 <TrendingUp className="w-3.5 h-3.5 text-emerald-500" />
 <span className="text-xs font-bold text-emerald-700">Well Covered</span>
 <span className="ml-auto text-2xs font-mono font-bold text-emerald-500 bg-emerald-100 px-1.5 py-0.5 rounded">{strongTopics.length}</span>
 </div>
 <div className="flex flex-wrap gap-1 max-h-20 overflow-y-auto">
 {strongTopics.slice(0, 8).map((t) => (
 <span key={t} className="text-2xs bg-emerald-100 text-emerald-700 px-1.5 py-0.5 rounded">{t}</span>
 ))}
 </div>
 </div>
 )}
 </div>
 )}

 {/* ── Color legend ── */}
 <div className="flex items-center gap-3 mb-4">
 <span className="text-2xs font-semibold text-slate-400 uppercase">Novice</span>
 <div className="flex gap-0.5">
 {[0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0].map((v) => (
 <div
 key={v}
 className="w-6 h-4 rounded-sm first:rounded-l-md last:rounded-r-md" style={{ backgroundColor: getHeatColor(v, isDark) }}
 />
 ))}
 </div>
 <span className="text-2xs font-semibold text-slate-400 uppercase">Expert</span>
 {sortByTopic && (
 <button
 onClick={() => setSortByTopic(null)}
 className="ml-2 text-2xs text-indigo-600 hover:underline" >
 Clear topic sort: {sortByTopic}
 </button>
 )}
 </div>

 {/* ── Heatmap table ── */}
 <div className="overflow-auto border border-default rounded-xl shadow-sm">
 <table className="min-w-full border-collapse">
 <thead>
 <tr>
 <th className="sticky left-0 z-20 bg-elevated px-3 py-3 text-left text-xs font-bold text-slate-600 border-b border-r border-default min-w-[180px]">
 <button onClick={() => handleSort("name")} className="flex items-center gap-1 hover:text-indigo-600 transition-colors">
 Member
 {sortBy ==="name" && !sortByTopic && (sortDir ==="desc" ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />)}
 </button>
 </th>
 {activeTopics.map((topic) => {
 const isBusRisk = busFactor.some((bf) => bf.topic === topic);
 const isGap = gapTopics.includes(topic);
 const isSorted = sortByTopic === topic;
 return (
 <th
 key={topic}
 className={`px-1 py-2 text-center border-b border-default min-w-[68px] transition-colors cursor-pointer group ${
 hoveredCol === topic ? "bg-indigo-50" : "" } ${isSorted ? "bg-violet-50" : ""}`}
 onMouseEnter={() => setHoveredCol(topic)}
 onMouseLeave={() => setHoveredCol(null)}
 onClick={() => handleTopicSort(topic)}
 >
 <div className="flex flex-col items-center gap-0.5 relative">
 {/* Bus factor warning badge */}
 {showGaps && isBusRisk && (
 <div className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full flex items-center justify-center" title="Bus factor risk">
 <span className="text-white text-[6px] font-bold">!</span>
 </div>
 )}
 {showGaps && isGap && !isBusRisk && (
 <div className="absolute -top-1 -right-1 w-3 h-3 bg-amber-500 rounded-full" title="Knowledge gap" />
 )}
 <span
 className={`text-2xs font-medium block max-w-[60px] truncate transition-colors ${
 isSorted ? "text-violet-600 font-bold" : "text-slate-500" }`}
 title={topic}
 style={{ writingMode: "vertical-rl", textOrientation: "mixed", transform: "rotate(180deg)", height: "70px", lineHeight: "1.2" }}
 >
 {topic}
 </span>
 {/* Sort indicator */}
 {isSorted && (
 <div className="mt-0.5">
 {sortDir ==="desc" ? <ChevronDown className="w-3 h-3 text-violet-500" /> : <ChevronUp className="w-3 h-3 text-violet-500" />}
 </div>
 )}
 {/* Sort icon on hover */}
 {!isSorted && (
 <ArrowUpDown className="w-2.5 h-2.5 text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity mt-0.5" />
 )}
 </div>
 </th>
 );
 })}
 {/* Sparkline column */}
 <th className="px-2 py-3 text-center text-2xs font-bold text-slate-500 uppercase border-b border-l border-default min-w-[80px]">
 Profile
 </th>
 <th className="sticky right-0 z-20 bg-elevated px-3 py-3 text-center text-2xs font-bold text-slate-500 uppercase border-b border-l border-default min-w-[70px]">
 <button onClick={() => handleSort("total")} className="flex items-center gap-0.5 mx-auto hover:text-indigo-600 transition-colors">
 Total
 {sortBy ==="total" && !sortByTopic && (sortDir ==="desc" ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />)}
 </button>
 </th>
 </tr>
 </thead>
 <tbody>
 {sortedMembers.map((member, idx) => {
 const total = memberTotals.get(member.id) || 0;
 const isRowHovered = hoveredRow === member.id;
 const sparkValues = activeTopics.map((t) => member.scores[t] || 0);
 const topicCount = activeTopics.filter((t) => (member.scores[t] || 0) > 0).length;

 return (
 <tr
 key={member.id}
 className={`transition-colors ${isRowHovered ? "bg-subtle/60" : idx % 2 === 0 ? "" : "bg-slate-50/30"}`}
 onMouseEnter={() => setHoveredRow(member.id)}
 onMouseLeave={() => setHoveredRow(null)}
 >
 <td className={`sticky left-0 z-10 px-3 py-2 border-r border-default ${isRowHovered ? "bg-subtle/60" : "bg-elevated"}`}>
 <button
 onClick={() => navigate(`/members/${member.id}`)}
 className="flex items-center gap-2.5 group" >
 <div
 className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 shadow-sm" style={{ backgroundColor: getAvatarColor(member.name) }}
 >
 <span className="text-2xs font-bold text-white">{getInitials(member.name)}</span>
 </div>
 <div className="text-left">
 <span className="text-xs font-semibold text-slate-700 group-hover:text-indigo-600 :text-indigo-400 transition-colors block truncate max-w-[100px]">
 {member.name}
 </span>
 <span className="text-2xs text-slate-400">{topicCount} topics</span>
 </div>
 </button>
 </td>
 {activeTopics.map((topic) => {
 const score = member.scores[topic] || 0;
 const isCellHovered = hoveredCell?.member === member.id && hoveredCell?.topic === topic;
 const isColHighlighted = hoveredCol === topic;
 const isBusTopic = busFactor.some((bf) => bf.topic === topic && bf.expert === member.name);
 const isCrossHair = (isRowHovered && isColHighlighted);

 return (
 <td
 key={topic}
 className="px-0.5 py-0.5" onMouseEnter={() => { setHoveredCell({ member: member.id, topic }); setHoveredCol(topic); }}
 onMouseLeave={() => { setHoveredCell(null); setHoveredCol(null); }}
 >
 <div
 className={`w-full h-9 rounded-md flex items-center justify-center text-2xs font-mono font-semibold transition-all relative ${
 isCellHovered ? "ring-2 ring-indigo-500 ring-offset-1 scale-110 z-10" : "" } ${isCrossHair && !isCellHovered ? "ring-1 ring-indigo-300" : ""} ${isColHighlighted && !isCellHovered && !isCrossHair ? "ring-1 ring-indigo-200" : ""}`}
 style={{
 backgroundColor: getHeatColor(score, isDark),
 color: getTextColor(score, isDark),
 }}
 title={`${member.name} — ${topic}: ${Math.round(score * 100)}%`}
 >
 {score > 0 ? Math.round(score * 100) : ""}
 {/* Bus factor badge */}
 {showGaps && isBusTopic && score > 0 && (
 <div className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-red-500 rounded-full flex items-center justify-center shadow-sm" title="Sole expert!">
 <AlertTriangle className="w-2 h-2 text-white" />
 </div>
 )}
 </div>
 </td>
 );
 })}
 {/* Sparkline */}
 <td className="px-2 py-2 border-l border-default text-center">
 <Sparkline values={sparkValues} />
 </td>
 <td className={`sticky right-0 z-10 px-3 py-2 border-l border-default text-center ${isRowHovered ? "bg-subtle/60" : "bg-elevated"}`}>
 <span className="text-xs font-bold text-slate-600 tabular-nums">{total.toFixed(1)}</span>
 </td>
 </tr>
 );
 })}
 {/* Team average row */}
 <tr className="border-t-2 border-default bg-subtle">
 <td className="sticky left-0 z-10 bg-subtle px-3 py-2 border-r border-default">
 <div className="flex items-center gap-2">
 <Users className="w-4 h-4 text-slate-400" />
 <span className="text-xs font-bold text-slate-500 italic">Team Average</span>
 </div>
 </td>
 {activeTopics.map((topic) => {
 const avg = topicAverages.get(topic) || 0;
 return (
 <td key={topic} className="px-0.5 py-0.5">
 <div
 className="w-full h-9 rounded-md flex items-center justify-center text-2xs font-mono font-semibold" style={{
 backgroundColor: getHeatColor(avg, isDark),
 color: getTextColor(avg, isDark),
 }}
 >
 {avg > 0 ? Math.round(avg * 100) : ""}
 </div>
 </td>
 );
 })}
 <td className="px-2 py-2 border-l border-default" />
 <td className="sticky right-0 z-10 bg-subtle px-3 py-2 border-l border-default" />
 </tr>
 </tbody>
 </table>
 </div>

 {/* ── Hover tooltip ── */}
 {hoveredCell && (() => {
 const member = sortedMembers.find((m) => m.id === hoveredCell.member);
 if (!member) return null;
 const score = member.scores[hoveredCell.topic] || 0;
 const isBus = busFactor.some((bf) => bf.topic === hoveredCell.topic && bf.expert === member.name);
 return (
 <div className="mt-3 inline-flex items-center gap-2 px-3 py-2 bg-elevated border border-default rounded-lg shadow-sm">
 <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: getHeatColor(score, isDark) }} />
 <span className="text-xs">
 <span className="font-semibold text-slate-700">{member.name}</span>
 {" → "}
 <span className="font-semibold text-indigo-600">{hoveredCell.topic}</span>
 {": "}
 <span className="font-mono font-bold">{Math.round(score * 100)}%</span>
 {score > 0.7 && <span className="ml-1.5 text-2xs text-emerald-600 font-medium">Expert</span>}
 {score > 0 && score <= 0.3 && <span className="ml-1.5 text-2xs text-amber-600 font-medium">Novice</span>}
 {isBus && <span className="ml-1.5 text-2xs text-red-600 font-medium">⚠ Sole Expert</span>}
 </span>
 </div>
 );
 })()}
 </div>
 );
}
