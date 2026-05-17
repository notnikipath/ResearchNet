import React, { useEffect, useMemo, useState } from "react";

import { ForceGraph } from "../components/ForceGraph";
import { KpiCard } from "../components/KpiCard";
import { TaskBoard } from "../components/TaskBoard";
import { TrendBars } from "../components/TrendBars";

const runtimeHost = typeof window !== "undefined" ? window.location.hostname : "localhost";
const runtimeProtocol = typeof window !== "undefined" ? window.location.protocol : "http:";
const runtimePort = typeof window !== "undefined" ? window.location.port : "";
const defaultGatewayPort = runtimePort === "31108" ? "31100" : "8500";
const gatewayUrl = import.meta.env.VITE_API_GATEWAY_URL || `${runtimeProtocol}//${runtimeHost}:${defaultGatewayPort}`;

const emptyDashboard = {
  paper: {
    paper_id: "PPR-DEMO-001",
    title: "ResearchNet demo paper",
    source_name: "Journal of Scholarly Data",
    year: 2024,
    topics: [],
    citations_count: 0,
  },
  recommendations: { items: [] },
  citation_graph: { nodes: [], links: [] },
  key_works: { items: [] },
  coauthors: { nodes: [], links: [] },
  trends: { items: [] },
  overview: {
    papers_total: 0,
    citation_edges_total: 0,
    top_topics: [],
    coauthor_nodes: 0,
    coauthor_links: 0,
  },
  user: { user_id: "USR-001", name: "Researcher" },
  favorites: { count: 0, items: [] },
  subscriptions: { count: 0, items: [] },
  notifications: { count: 0, items: [] },
  search_quality: {
    ndcg_at_10: 0,
    precision_at_10: 0,
    meets_ndcg_target: false,
    meets_precision_target: false,
  },
};

async function loadDashboard(paperId, userId) {
  const response = await fetch(`${gatewayUrl}/dashboard/${paperId}/${userId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch dashboard: ${response.status}`);
  }
  return response.json();
}

export function DashboardPage() {
  const [paperId, setPaperId] = useState("PPR-DEMO-001");
  const [userId, setUserId] = useState("USR-001");
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const [dashboard, setDashboard] = useState(emptyDashboard);

  useEffect(() => {
    let active = true;

    loadDashboard(paperId, userId)
      .then((payload) => {
        if (!active) {
          return;
        }
        setDashboard({ ...emptyDashboard, ...payload });
        setStatus("succeeded");
        setError(null);
      })
      .catch((err) => {
        if (!active) {
          return;
        }
        setStatus("failed");
        setError(err.message);
      });

    return () => {
      active = false;
    };
  }, [paperId, userId]);

  const recommendations = dashboard.recommendations?.items || [];
  const statusLabel = useMemo(() => {
    if (status === "loading") {
      return "loading";
    }
    if (status === "failed") {
      return "fallback";
    }
    return "live";
  }, [status]);

  const refresh = async () => {
    try {
      setStatus("loading");
      const payload = await loadDashboard(paperId, userId);
      setDashboard({ ...emptyDashboard, ...payload });
      setStatus("succeeded");
      setError(null);
    } catch (err) {
      setStatus("failed");
      setError(err.message);
    }
  };

  return (
    <div className="app">
      <div className="background-veil veil-a" />
      <div className="background-veil veil-b" />

      <header className="hero reveal">
        <div className="hero-copy">
          <p className="eyebrow">ResearchNet Intelligence Platform</p>
          <h1>Scientific discovery map: search, citation graph, recommendations, and trend forecasting.</h1>
          <p className="sub">
            Unified workspace for journals, conferences, preprints, patents, and book chapters. Pipeline quality is tracked
            through ranking metrics and graph analytics.
          </p>
          <div className="hero-badges">
            <span>Semantic search</span>
            <span>Citation intelligence</span>
            <span>Expert recommendations</span>
            <span>Multilingual metadata</span>
          </div>
        </div>

        <div className="hero-panel">
          <label>
            Paper ID
            <input value={paperId} onChange={(event) => setPaperId(event.target.value)} placeholder="PPR-DEMO-001" />
          </label>
          <label>
            User ID
            <input value={userId} onChange={(event) => setUserId(event.target.value)} placeholder="USR-001" />
          </label>
          <div className="hero-actions">
            <button onClick={refresh}>Refresh dashboard</button>
          </div>
          <p className="status-line">Status: {statusLabel}</p>
        </div>
      </header>

      <section className="kpi-grid">
        <KpiCard
          title="Search NDCG@10"
          value={Number(dashboard.search_quality?.ndcg_at_10 || 0).toFixed(2)}
          target="Target > 0.80"
          ok={Boolean(dashboard.search_quality?.meets_ndcg_target)}
        />
        <KpiCard
          title="Precision@10"
          value={`${Math.round((dashboard.search_quality?.precision_at_10 || 0) * 100)}%`}
          target="Target > 70%"
          ok={Boolean(dashboard.search_quality?.meets_precision_target)}
        />
        <KpiCard
          title="Indexed Papers"
          value={dashboard.overview?.papers_total || 0}
          target="Scalable to 10M"
          ok={Number(dashboard.overview?.papers_total || 0) <= 10000000}
        />
        <KpiCard
          title="Citation Edges"
          value={dashboard.overview?.citation_edges_total || 0}
          target="Graph is connected"
          ok={Number(dashboard.overview?.citation_edges_total || 0) > 0}
        />
      </section>

      {error ? <div className="error-banner">{error}</div> : null}

      <section className="content-grid">
        <article className="panel panel-featured reveal delay-1">
          <div className="panel-head compact">
            <div>
              <p className="section-kicker">Publication Card</p>
              <h2>{dashboard.paper?.title || "Unknown paper"}</h2>
            </div>
            <span className="pill">{dashboard.paper?.paper_id}</span>
          </div>
          <p className="panel-copy">
            Source: {dashboard.paper?.source_name} ({dashboard.paper?.year}). Citations: {dashboard.paper?.citations_count || 0}.
          </p>
          <div className="metrics-row">
            <div>
              <strong>{dashboard.favorites?.count || 0}</strong>
              <span>favorites</span>
            </div>
            <div>
              <strong>{dashboard.subscriptions?.count || 0}</strong>
              <span>subscriptions</span>
            </div>
            <div>
              <strong>{dashboard.overview?.coauthor_nodes || 0}</strong>
              <span>authors</span>
            </div>
            <div>
              <strong>{dashboard.overview?.coauthor_links || 0}</strong>
              <span>coauthor links</span>
            </div>
          </div>
          <TaskBoard recommendations={recommendations} />
        </article>

        <article className="panel reveal delay-2">
          <div className="panel-head compact">
            <div>
              <p className="section-kicker">Coauthor Graph</p>
              <h2>Interactive network</h2>
            </div>
            <span className="pill accent">D3 force</span>
          </div>
          <ForceGraph nodes={dashboard.coauthors?.nodes || []} links={dashboard.coauthors?.links || []} />
        </article>

        <article className="panel reveal delay-3">
          <div className="panel-head compact">
            <div>
              <p className="section-kicker">Topic Trends</p>
              <h2>Emerging directions</h2>
            </div>
            <span className="pill accent">Forecast-ready</span>
          </div>
          <TrendBars items={dashboard.trends?.items || []} />
        </article>

        <article className="panel panel-analytics reveal delay-4">
          <div className="panel-head compact">
            <div>
              <p className="section-kicker">Notifications</p>
              <h2>Subscriber activity</h2>
            </div>
            <span className="pill">{dashboard.notifications?.count || 0} alerts</span>
          </div>
          <div className="timeline-list">
            {(dashboard.notifications?.items || []).slice(-6).reverse().map((item, index) => (
              <div className="stack-item" key={`${item.payload_id}-${index}`}>
                <div>
                  <p className="stack-title">{item.subject}</p>
                  <p className="stack-sub">{item.body}</p>
                </div>
                <span>{item.alert_type}</span>
              </div>
            ))}
            {!(dashboard.notifications?.items || []).length ? <div className="empty-board">No notifications yet.</div> : null}
          </div>
        </article>
      </section>
    </div>
  );
}
