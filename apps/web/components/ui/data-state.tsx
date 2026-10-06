"use client";

import React from "react";
import { AlertCircle, RefreshCw, Inbox, LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TableRow, TableCell } from "@/components/ui/table";

interface DataAlertProps {
  error: string | null | undefined;
  onRetry?: () => void;
  className?: string;
}

export function DataAlert({ error, onRetry, className = "" }: DataAlertProps) {
  if (!error) return null;

  return (
    <div
      role="alert"
      className={`p-4 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive text-sm flex items-center justify-between gap-4 ${className}`}
    >
      <div className="flex items-center gap-2.5">
        <AlertCircle className="w-4 h-4 shrink-0" />
        <span>{error}</span>
      </div>
      {onRetry && (
        <Button
          variant="outline"
          size="sm"
          onClick={onRetry}
          className="shrink-0 h-8 gap-1.5 border-destructive/30 hover:bg-destructive/10 text-destructive"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Retry</span>
        </Button>
      )}
    </div>
  );
}

interface TableLoadingStateProps {
  colSpan: number;
  message?: string;
}

export function TableLoadingState({ colSpan, message = "Loading data..." }: TableLoadingStateProps) {
  return (
    <TableRow>
      <TableCell colSpan={colSpan} className="text-center py-10 text-muted-foreground animate-pulse">
        <div className="flex items-center justify-center gap-2">
          <RefreshCw className="w-4 h-4 animate-spin text-primary" />
          <span>{message}</span>
        </div>
      </TableCell>
    </TableRow>
  );
}

interface TableEmptyStateProps {
  colSpan: number;
  message?: string;
}

export function TableEmptyState({ colSpan, message = "No records found." }: TableEmptyStateProps) {
  return (
    <TableRow>
      <TableCell colSpan={colSpan} className="text-center py-10 text-muted-foreground">
        <div className="flex flex-col items-center justify-center gap-1.5 py-4">
          <Inbox className="w-8 h-8 text-muted-foreground/50 mb-1" />
          <p className="text-sm font-medium">{message}</p>
        </div>
      </TableCell>
    </TableRow>
  );
}

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: LucideIcon;
  action?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
}

export function EmptyState({
  title,
  description,
  icon: Icon = Inbox,
  action,
  className = "",
}: EmptyStateProps) {
  return (
    <div className={`flex flex-col items-center justify-center text-center p-8 border border-dashed rounded-lg bg-card/50 ${className}`}>
      <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-3">
        <Icon className="w-6 h-6 text-muted-foreground" />
      </div>
      <h3 className="font-semibold text-base mb-1">{title}</h3>
      {description && <p className="text-sm text-muted-foreground max-w-sm mb-4">{description}</p>}
      {action && (
        <Button size="sm" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  );
}
