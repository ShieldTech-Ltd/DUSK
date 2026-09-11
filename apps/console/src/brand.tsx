import duskLogo from "../../../docs/dusk-logo.svg";

export function DuskMark({ className = "" }: { className?: string }) {
  return (
    <span className={`dusk-mark ${className}`.trim()} aria-hidden="true">
      <img src={duskLogo} alt="" />
    </span>
  );
}
