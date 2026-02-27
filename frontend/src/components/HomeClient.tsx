"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import MapClient from "@/components/MapClient";

type Lang = "tr" | "en";

type Copy = {
  badge: string;
  title: string;
  subtitle: string;
  chatAgent1: string;
  chatUser: string;
  chatAgent2: string;
  inputPlaceholder: string;
  askButton: string;
  modelLabel: string;
  modelPlaceholder: string;
  statusIdle: string;
  statusThinking: string;
  statusError: string;
  mapTitle: string;
  mapMeta: string;
};

const COPY: Record<Lang, Copy> = {
  tr: {
    badge: "Agentic Map",
    title: "Harita Asistanı",
    subtitle: "Doğal dilde sor, agent sonuçları haritada gör.",
    chatAgent1: "Merhaba! Sana en iyi mekanları bulabilirim. Nerede arayalım?",
    chatUser: "Kadıköy’de sakin kahveciler.",
    chatAgent2: "Haritada işaretledim. İstersen fiyat aralığı da ekleyebilirim.",
    inputPlaceholder: "Örn: Beşiktaş’ta açık kafeler",
    askButton: "Sor",
    modelLabel: "Model",
    modelPlaceholder: "OpenRouter model adı",
    statusIdle: "Hazır",
    statusThinking: "Düşünüyor…",
    statusError: "Hata",
    mapTitle: "Canlı Harita",
    mapMeta: "OpenStreetMap · Leaflet",
  },
  en: {
    badge: "Agentic Map",
    title: "Map Assistant",
    subtitle: "Ask in natural language, see agent results on the map.",
    chatAgent1: "Hi! I can find the best spots for you. Where should we look?",
    chatUser: "Quiet coffee places in Kadıköy.",
    chatAgent2: "I pinned them on the map. Want to add a price range?",
    inputPlaceholder: "e.g. Open cafes in Beşiktaş",
    askButton: "Ask",
    modelLabel: "Model",
    modelPlaceholder: "OpenRouter model name",
    statusIdle: "Ready",
    statusThinking: "Thinking…",
    statusError: "Error",
    mapTitle: "Live Map",
    mapMeta: "OpenStreetMap · Leaflet",
  },
};

type ChatMessage = {
  role: "user" | "agent";
  text: string;
};

type ModelOption = {
  id: string;
  name: string;
};

type MapCenter = {
  lat: number;
  lon: number;
  label?: string;
};

type Place = {
  name: string;
  lat: number | null;
  lon: number | null;
  address?: string;
};

export default function HomeClient() {
  const [lang, setLang] = useState<Lang>("en");
  const [hasInteracted, setHasInteracted] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [modelName, setModelName] = useState("openai/gpt-4o-mini");
  const [modelOptions, setModelOptions] = useState<ModelOption[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [modelOpen, setModelOpen] = useState(false);
  const [modelQuery, setModelQuery] = useState("");
  const [mapCenter, setMapCenter] = useState<MapCenter | null>(null);
  const [mapPlaces, setMapPlaces] = useState<Place[]>([]);
  const [status, setStatus] = useState<"idle" | "thinking" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const t = useMemo(() => COPY[lang], [lang]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);


  useEffect(() => {
    if (hasInteracted) {
      return;
    }
    setMessages([
      { role: "agent", text: t.chatAgent1 },
      { role: "user", text: t.chatUser },
      { role: "agent", text: t.chatAgent2 },
    ]);
  }, [t, hasInteracted]);

  useEffect(() => {
    let isMounted = true;
    const loadModels = async () => {
      setModelsLoading(true);
      setModelsError(null);
      try {
        const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
        const res = await fetch(`${baseUrl}/models/openrouter`);
        if (!res.ok) {
          throw new Error(`Model list failed (${res.status})`);
        }
        const data: { data?: ModelOption[] } = await res.json();
        if (isMounted && Array.isArray(data.data)) {
          setModelOptions(data.data);
          if (data.data.length > 0) {
            setModelName(data.data[0].id);
          }
        }
      } catch (err) {
        if (isMounted) {
          setModelOptions([]);
          setModelsError(err instanceof Error ? err.message : "Model list failed");
        }
      } finally {
        if (isMounted) {
          setModelsLoading(false);
        }
      }
    };

    loadModels();
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (modelOpen) {
      setModelOpen(false);
    }
  }, [modelName]);

  const handleSubmit = async () => {
    const prompt = input.trim();
    if (!prompt) return;
    setHasInteracted(true);
    setInput("");
    setError(null);
    setStatus("thinking");
    setMessages((prev) => [...prev, { role: "user", text: prompt }]);

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
      const res = await fetch(`${baseUrl}/agent/map`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, model_name: modelName }),
      });

      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        throw new Error(payload?.detail || `Request failed (${res.status})`);
      }

      const data: { response?: string; center?: MapCenter; places?: Place[] } = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: "agent", text: data.response || "No response." },
      ]);
      if (data.center && typeof data.center.lat === "number") {
        setMapCenter(data.center);
      }
      if (Array.isArray(data.places)) {
        setMapPlaces(data.places);
      }
      setStatus("idle");
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      handleSubmit();
    }
  };

  return (
    <main className="page">
      <section className="shell">
        <aside className="panel">
          <div className="panel-header">
            <div className="badge">{t.badge}</div>
            <div className="lang-toggle" role="group" aria-label="Language switch">
              <button
                type="button"
                className={lang === "tr" ? "active" : ""}
                onClick={() => setLang("tr")}
              >
                TR
              </button>
              <button
                type="button"
                className={lang === "en" ? "active" : ""}
                onClick={() => setLang("en")}
              >
                EN
              </button>
            </div>
            <h1>{t.title}</h1>
            <p>{t.subtitle}</p>
          </div>
          <div className="chat">
            {messages.map((message, idx) => (
              <div key={`${message.role}-${idx}`} className={`chat-bubble ${message.role}`}>
                {message.text}
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>
          <div className="controls">
            {modelOpen && <div className="model-overlay" onClick={() => setModelOpen(false)} />}
            <label className="model">
              <span>{t.modelLabel}</span>
              <div className={`model-select ${modelOpen ? "open" : ""}`}>
                <button
                  type="button"
                  className="model-trigger"
                  onClick={() => setModelOpen((prev) => !prev)}
                  disabled={modelsLoading || modelOptions.length === 0}
                >
                  <span>
                    {modelOptions.length === 0
                      ? modelsLoading
                        ? "Loading…"
                        : t.modelPlaceholder
                      : modelOptions.find((m) => m.id === modelName)?.name || modelName}
                  </span>
                  <span className="chevron">▾</span>
                </button>
                {modelOpen && modelOptions.length > 0 ? (
                  <>
                  <div className="model-menu" role="listbox">
                    <div className="model-search">
                      <input
                        type="text"
                        value={modelQuery}
                        onChange={(event) => setModelQuery(event.target.value)}
                        placeholder="Search models…"
                        aria-label="Search models"
                      />
                    </div>
                    {modelOptions
                      .filter((model) => {
                        const q = modelQuery.trim().toLowerCase();
                        if (!q) return true;
                        return (
                          model.name.toLowerCase().includes(q) ||
                          model.id.toLowerCase().includes(q)
                        );
                      })
                      .map((model) => (
                        <button
                          type="button"
                          key={model.id}
                          className={`model-option ${model.id === modelName ? "active" : ""}`}
                          onClick={() => {
                            setModelName(model.id);
                            setModelOpen(false);
                          }}
                        >
                          {model.name}
                        </button>
                      ))}
                  </div>
                  </>
                ) : null}
              </div>
            </label>
            {modelsError ? <div className="error">{modelsError}</div> : null}
            <div className={`status ${status}`}>
              {status === "idle" && t.statusIdle}
              {status === "thinking" && t.statusThinking}
              {status === "error" && t.statusError}
            </div>
            {error ? <div className="error">{error}</div> : null}
          </div>
          <form
            className="composer"
            onSubmit={(event) => {
              event.preventDefault();
              handleSubmit();
            }}
          >
            <input
              type="text"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t.inputPlaceholder}
              aria-label="Agent prompt"
            />
            <button type="submit">{t.askButton}</button>
          </form>
        </aside>
        <section className="map-area">
          <div className="map-header">
            <div className="title">{t.mapTitle}</div>
            <div className="meta">{t.mapMeta}</div>
          </div>
          <MapClient center={mapCenter} places={mapPlaces} />
        </section>
      </section>
    </main>
  );
}
