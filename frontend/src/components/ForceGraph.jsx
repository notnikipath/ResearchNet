import React, { useEffect, useRef } from "react";
import * as d3 from "d3";

export function ForceGraph({ nodes = [], links = [], width = 760, height = 360 }) {
  const ref = useRef(null);

  useEffect(() => {
    const svg = d3.select(ref.current);
    svg.selectAll("*").remove();

    if (!nodes.length) {
      svg
        .append("text")
        .attr("x", width / 2)
        .attr("y", height / 2)
        .attr("text-anchor", "middle")
        .attr("fill", "#4f5e59")
        .text("No coauthor data yet");
      return;
    }

    const linksData = links.map((link) => ({ ...link }));
    const nodesData = nodes.map((node) => ({ ...node }));

    const simulation = d3
      .forceSimulation(nodesData)
      .force("link", d3.forceLink(linksData).id((d) => d.id).distance(90).strength(0.3))
      .force("charge", d3.forceManyBody().strength(-180))
      .force("center", d3.forceCenter(width / 2, height / 2));

    const link = svg
      .append("g")
      .attr("stroke", "rgba(26, 82, 68, 0.35)")
      .selectAll("line")
      .data(linksData)
      .join("line")
      .attr("stroke-width", (d) => Math.max(1, d.weight || 1));

    const color = d3.scaleOrdinal(["#0a7a58", "#1b9aaa", "#d96f3b", "#235789", "#f39b6d"]);

    const node = svg
      .append("g")
      .selectAll("circle")
      .data(nodesData)
      .join("circle")
      .attr("r", (d) => 6 + Math.min(10, Number(d.papers || 0)))
      .attr("fill", (d) => color(d.group || d.affiliation || "group"))
      .attr("stroke", "#ffffff")
      .attr("stroke-width", 1.2)
      .call(
        d3
          .drag()
          .on("start", (event, d) => {
            if (!event.active) {
              simulation.alphaTarget(0.3).restart();
            }
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) {
              simulation.alphaTarget(0);
            }
            d.fx = null;
            d.fy = null;
          })
      );

    node.append("title").text((d) => `${d.label} (${d.papers || 0} papers)`);

    const labels = svg
      .append("g")
      .selectAll("text")
      .data(nodesData)
      .join("text")
      .text((d) => d.label)
      .attr("font-size", 11)
      .attr("fill", "#163328")
      .attr("dx", 10)
      .attr("dy", 4);

    simulation.on("tick", () => {
      link
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);

      node.attr("cx", (d) => d.x).attr("cy", (d) => d.y);
      labels.attr("x", (d) => d.x).attr("y", (d) => d.y);
    });

    return () => simulation.stop();
  }, [nodes, links, width, height]);

  return <svg ref={ref} viewBox={`0 0 ${width} ${height}`} className="force-graph" />;
}
