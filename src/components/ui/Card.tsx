import React from "react";
import { Icon, type IconName } from "./icons";

interface CardProps {
  title?: string;
  icon?: IconName;
  subtitle?: string;
  action?: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  children: React.ReactNode;
}

export function Card({
  title,
  icon,
  subtitle,
  action,
  className = "",
  bodyClassName = "",
  children,
}: CardProps) {
  return (
    <div
      className={`bg-white rounded-2xl shadow-card border border-slate-100 overflow-hidden ${className}`}
    >
      {(title || action) && (
        <div className="px-5 py-3.5 border-b border-slate-100 flex items-center justify-between gap-3 bg-slate-50/60">
          <div className="flex items-center gap-2.5 min-w-0">
            {icon && (
              <span className="shrink-0 w-8 h-8 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center">
                <Icon name={icon} size={18} />
              </span>
            )}
            <div className="min-w-0">
              {title && (
                <h3 className="font-semibold text-slate-800 truncate">{title}</h3>
              )}
              {subtitle && (
                <p className="text-xs text-slate-500 truncate">{subtitle}</p>
              )}
            </div>
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </div>
      )}
      <div className={`p-5 ${bodyClassName}`}>{children}</div>
    </div>
  );
}
