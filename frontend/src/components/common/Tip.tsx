/** Infobulle (?) cliquable/survol avec description detaillee */
export default function Tip({ text }: { text: string }) {
  return (
    <span className="relative inline-block ml-1 group cursor-help">
      <span className="text-[#555] text-[12px] border border-[#555] rounded-full w-[18px] h-[18px] inline-flex items-center justify-center hover:text-[#8888ff] hover:border-[#8888ff] transition-colors">
        ?
      </span>
      <span className="fixed hidden group-hover:block bg-[#1a1a2e] border border-[#4a4a6e] text-[#ccc] text-[14px] rounded px-3 py-2 w-[350px] shadow-2xl z-[9999] leading-tight whitespace-normal"
        style={{ bottom: "80px", left: "50%", transform: "translateX(-50%)" }}>
        {text}
      </span>
    </span>
  );
}
