import React, { useEffect, useRef } from "react";
import * as d3 from "d3";

export function TrendBars({ items = [], width = 760, height = 280 }) {
  const ref = useRef(null);

  useEffect(() => {
    const svg = d3.select(ref.current);
    svg.selectAll("*").remove();

    const top = items.slice(0, 6).map((item) => ({
      topic: item.topic,
      value: item.latest || item.points?.[item.points.length - 1]?.count || 0,
    }));

    if (!top.length) {
      svg
        .append("text")
        .attr("x", width / 2)
        .attr("y", height / 2)
        .attr("text-anchor", "middle")
        .attr("fill", "#4f5e59")
        .text("No trend data yet");
      return;
    }

    const margin = { top: 18, right: 20, bottom: 64, left: 46 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    const defs = svg.append("defs");
    const gradient = defs.append("linearGradient").attr("id", "trendGradient").attr("x1", "0%").attr("x2", "0%").attr("y1", "0%").attr("y2", "100%");
    gradient.append("stop").attr("offset", "0%").attr("stop-color", "#1aa17f");
    gradient.append("stop").attr("offset", "100%").attr("stop-color", "#0f6d57");

    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

    const x = d3.scaleBand().domain(top.map((d) => d.topic)).range([0, innerWidth]).padding(0.22);
    const y = d3
      .scaleLinear()
      .domain([0, d3.max(top, (d) => d.value) || 1])
      .nice()
      .range([innerHeight, 0]);

    g.append("g")
      .attr("transform", `translate(0,${innerHeight})`)
      .call(d3.axisBottom(x))
      .selectAll("text")
      .style("text-anchor", "end")
      .attr("transform", "rotate(-24)")
      .attr("dx", "-0.6em")
      .attr("dy", "0.3em");

    g.append("g").call(d3.axisLeft(y).ticks(5));

    g.selectAll("rect")
      .data(top)
      .join("rect")
      .attr("x", (d) => x(d.topic))
      .attr("y", (d) => y(d.value))
      .attr("width", x.bandwidth())
      .attr("height", (d) => innerHeight - y(d.value))
      .attr("rx", 8)
      .attr("fill", "url(#trendGradient)");
  }, [items, width, height]);

  return <svg ref={ref} viewBox={`0 0 ${width} ${height}`} className="trend-bars" />;
}
