import React from "react";
import { Icon, type IconName } from "./icons";

export function EmptyState({
  icon = "sparkles",
  title,
  description,
  children,
  className = "",
}: {
  icon?: IconName;
  title: string;
  description?: string;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center text-center py-16 px-6 ${className}`}
    >
      <div className="w-16 h-16 rounded-2xl bg-brand-50 text-brand-500 flex items-center justify-center mb-5">
        <Icon name={icon} size={30} />
      </div>
      <h3 className="text-lg font-semibold text-slate-800">{title}</h3>
      {description && (
        <p className="text-slate-500 max-w-md mt-2 leading-relaxed">{description}</p>
      )}
      {children && <div className="mt-6">{children}</div>}
    </div>
  );
}
