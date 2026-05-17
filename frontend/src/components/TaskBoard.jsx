import React from "react";

export function TaskBoard({ recommendations }) {
  if (!recommendations?.length) {
    return <div className="empty-board">No recommendation candidates yet. Process a paper in the workflow first.</div>;
  }

  return (
    <section className="route-lane">
      {recommendations.map((item, index) => (
        <article className="route-stop" key={`${item.paper_id}-${index}`}>
          <div>
            <p className="lesson-type">Rank {index + 1}</p>
            <h4>{item.paper_id}</h4>
            <div className="lesson-meta">
              <span>{item.reason}</span>
              <span>{(item.shared_topics || []).join(", ") || "topic overlap"}</span>
            </div>
          </div>
          <strong>{Number(item.score || 0).toFixed(3)}</strong>
        </article>
      ))}
    </section>
  );
}
