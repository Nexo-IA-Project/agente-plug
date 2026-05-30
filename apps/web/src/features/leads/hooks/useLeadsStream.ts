"use client";

import { useEffect, useRef, useState } from "react";
import { API_URL } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { Lead, LeadEvent, LeadFilters } from "../types";

type ConnectionStatus = "connecting" | "open" | "reconnecting" | "closed";

interface EnrollmentUpdatePayload {
  id: string;
  status: string;
  step_id: string;
  step_status: string;
  step_label?: string;
}

interface Handlers {
  onLeadUpserted?: (lead: Lead, isNew: boolean) => void;
  onEventAppended?: (leadId: string, event: LeadEvent) => void;
  onEnrollmentUpdated?: (
    leadId: string,
    enrollment: EnrollmentUpdatePayload,
  ) => void;
}

function buildUrl(filters: LeadFilters): string {
  const qs = new URLSearchParams();
  if (filters.product_id) qs.set("product_id", filters.product_id);
  if (filters.status) qs.set("status", filters.status);
  if (filters.utm_source) qs.set("utm_source", filters.utm_source);
  if (filters.date_from) qs.set("date_from", filters.date_from);
  if (filters.date_to) qs.set("date_to", filters.date_to);
  if (filters.unmatched) qs.set("unmatched", "true");
  // EventSource não consegue mandar header Authorization; passa JWT na query.
  const token = getToken();
  if (token) qs.set("token", token);
  return `${API_URL}/admin/leads/stream?${qs.toString()}`;
}

export function useLeadsStream(filters: LeadFilters, handlers: Handlers) {
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    const es = new EventSource(buildUrl(filters), { withCredentials: true });
    setStatus("connecting");

    es.onopen = () => setStatus("open");
    es.onerror = () => setStatus("reconnecting");

    es.addEventListener("lead.upserted", (e) => {
      try {
        const env = JSON.parse((e as MessageEvent).data);
        handlersRef.current.onLeadUpserted?.(env.lead, env.is_new);
        if (env.event) {
          handlersRef.current.onEventAppended?.(env.lead.id, env.event);
        }
      } catch {
        // ignore JSON errors
      }
    });

    es.addEventListener("lead.enrollment.updated", (e) => {
      try {
        const env = JSON.parse((e as MessageEvent).data);
        handlersRef.current.onEnrollmentUpdated?.(
          env.lead_id ?? "",
          env.enrollment,
        );
      } catch {
        // ignore JSON errors
      }
    });

    return () => {
      es.close();
    };
  }, [
    filters.product_id,
    filters.status,
    filters.utm_source,
    filters.date_from,
    filters.date_to,
    filters.unmatched,
  ]);

  return { status };
}
