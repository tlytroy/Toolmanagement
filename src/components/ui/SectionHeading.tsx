export function SectionHeading({
  eyebrow,
  title,
  description,
  className = "",
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  className?: string;
}) {
  return (
    <div className={`text-center ${className}`}>
      {eyebrow && (
        <p className="text-sm font-semibold text-brand-600 tracking-wide uppercase mb-2">
          {eyebrow}
        </p>
      )}
      <h1 className="text-3xl font-bold text-slate-800">{title}</h1>
      {description && (
        <p className="text-slate-500 max-w-2xl mx-auto mt-3 leading-relaxed">
          {description}
        </p>
      )}
    </div>
  );
}
