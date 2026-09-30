import {
  Chart as ChartJS,
  ArcElement,
  BarElement,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";
import { Doughnut, Bar, Line } from "react-chartjs-2";

ChartJS.register(
  ArcElement, BarElement, CategoryScale, LinearScale,
  PointElement, LineElement, Tooltip, Legend, Filler
);

ChartJS.defaults.font.family = "'Inter', sans-serif";
ChartJS.defaults.color = "#64748b";

const CLASS_COLORS = {
  Forest: "#2E7D32",
  Water: "#1565C0",
  Agriculture: "#FBC02D",
  Urban: "#E53935",
  Others: "#9E9E9E",
};

export function LandCoverDonut({ data }) {
  const labels = Object.keys(data || {});
  const values = labels.map((k) => data[k]);
  const colors = labels.map((k) => CLASS_COLORS[k] || "#9E9E9E");
  return (
    <Doughnut
      data={{
        labels,
        datasets: [
          {
            data: values,
            backgroundColor: colors,
            borderWidth: 2,
            borderColor: "#fff",
            hoverOffset: 6,
          },
        ],
      }}
      options={{
        cutout: "62%",
        plugins: {
          legend: { position: "right", labels: { boxWidth: 12, padding: 12, font: { size: 12 } } },
          tooltip: { callbacks: { label: (c) => ` ${c.label}: ${c.parsed.toFixed(1)}%` } },
        },
      }}
    />
  );
}

export function AreaChangeBar({ deltas }) {
  const labels = Object.keys(deltas || {});
  const values = labels.map((k) => deltas[k]);
  const colors = values.map((v) => (v >= 0 ? "#2E7D32" : "#E53935"));
  return (
    <Bar
      data={{
        labels,
        datasets: [
          {
            label: "Δ area (%) vs previous",
            data: values,
            backgroundColor: colors,
            borderRadius: 6,
            maxBarThickness: 46,
          },
        ],
      }}
      options={{
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false } },
          y: { grid: { color: "#eef2f7" }, ticks: { callback: (v) => v + "%" } },
        },
      }}
    />
  );
}

export function ConfidenceLine({ trend }) {
  const labels = (trend || []).map((t, i) => t.name?.slice(0, 10) || `#${i + 1}`);
  const values = (trend || []).map((t) => t.confidence);
  return (
    <Line
      data={{
        labels,
        datasets: [
          {
            label: "Confidence %",
            data: values,
            borderColor: "#1565C0",
            backgroundColor: "rgba(21,101,192,0.12)",
            fill: true,
            tension: 0.35,
            pointRadius: 3,
            pointBackgroundColor: "#1565C0",
          },
        ],
      }}
      options={{
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false } },
          y: { min: 0, max: 100, grid: { color: "#eef2f7" }, ticks: { callback: (v) => v + "%" } },
        },
      }}
    />
  );
}

export function ObjectsBar({ counts }) {
  const labels = Object.keys(counts || {});
  const values = labels.map((k) => counts[k]);
  return (
    <Bar
      data={{
        labels,
        datasets: [
          {
            label: "Detections",
            data: values,
            backgroundColor: "#2AA7FF",
            borderRadius: 6,
            maxBarThickness: 40,
          },
        ],
      }}
      options={{
        indexAxis: "y",
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: "#eef2f7" }, ticks: { precision: 0 } },
          y: { grid: { display: false } },
        },
      }}
    />
  );
}
