import { Frame } from "@/components/frame";

export default function NotFound() {
  return (
    <div className="login-screen">
      <Frame className="login-panel">
        <div className="stack">
          <h1 className="page-title">Página no encontrada</h1>
          <p className="page-tagline">La ruta no existe.</p>
          <a className="btn btn-primary" href="/sitios">
            Volver
          </a>
        </div>
      </Frame>
    </div>
  );
}
