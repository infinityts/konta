import { AccordionLoaderColor } from "@/components/loading-ui/accordion-loader-color";

/**
 * Pantalla de carga de la aplicación.
 *
 * Se usa como `fallback` de `Suspense` (mientras baja el código de una página)
 * y en cualquier punto donde haya que esperar datos.
 */
export function Cargando({
  texto = "Cargando…",
  completo = false,
}: {
  texto?: string;
  /** `true` ocupa toda la ventana (pantalla completa). */
  completo?: boolean;
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-6 ${
        completo ? "min-h-screen" : "min-h-[55vh]"
      }`}
    >
      <AccordionLoaderColor />
      <p className="text-sm text-slate-500">{texto}</p>
    </div>
  );
}

export default Cargando;
