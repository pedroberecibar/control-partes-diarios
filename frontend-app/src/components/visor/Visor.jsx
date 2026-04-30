import { useEffect, useRef, useState } from 'react';
import { Icon, PARTE_ESTADO_CONFIG, StatusChip, TRAZA_CONFIG } from '../Icon';
import { OBSERVACIONES_LABELS, getMockObs, getPartePhotos } from '../../data/visorMock';
import { getVisor } from '../../api/partesApi';

function mapApiObs(apiObs) {
  if (!apiObs) return null;
  return {
    gabinete:    apiObs.gabinete    ?? false,
    subterraneo: apiObs.subterraneo ?? false,
    altura:      apiObs.altura      ?? false,
    aereo:       apiObs.aereo       ?? false,
    eq_reempl:   apiObs.equipo_medicion_reemplazado ?? false,
    acom_real:   apiObs.acometida_realizada          ?? false,
    tapa_reempl: apiObs.tapa_reemplazada             ?? false,
    med_reg:     apiObs.equipo_medicion_instalado    ?? false,
  };
}

// ── Tira de thumbnails portrait ─────────────────────────────────
function ThumbnailStrip({ photos, activeIdx, onSelect, size = 64 }) {
  return (
    <div style={{ display: 'flex', gap: 6, justifyContent: 'center', padding: '10px 0 4px', flexShrink: 0 }}>
      {photos.map((src, i) => {
        const active = i === activeIdx;
        return (
          <div
            key={i}
            onClick={() => onSelect(i)}
            style={{
              width: size,
              height: size * 1.33,
              borderRadius: 4,
              overflow: 'hidden',
              cursor: 'pointer',
              flexShrink: 0,
              border: active ? '2px solid #3a9e6e' : '2px solid rgba(255,255,255,0.12)',
              transform: active ? 'translateY(-2px)' : 'none',
              boxShadow: active ? '0 4px 12px rgba(0,0,0,0.4)' : 'none',
              transition: 'all 0.15s ease',
              opacity: active ? 1 : 0.72,
            }}
          >
            <img
              src={src}
              alt={`Foto ${i + 1}`}
              style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
              loading="lazy"
            />
          </div>
        );
      })}
    </div>
  );
}

// ── Visor principal: zoom + pan + rotación + fullscreen ───────────
export function ImageViewer({ photos, embedded = false, parteId, initialIdx = 0, onClose }) {
  const [idx, setIdx]               = useState(initialIdx);
  const [zoom, setZoom]             = useState(1);
  const [rotation, setRotation]     = useState(0);
  const [pan, setPan]               = useState({ x: 0, y: 0 });
  const [dragging, setDragging]     = useState(false);
  const [dragStart, setDragStart]   = useState({ x: 0, y: 0 });
  const [panStart, setPanStart]     = useState({ x: 0, y: 0 });
  const [fullscreen, setFullscreen] = useState(false);
  const [imgLoaded, setImgLoaded]   = useState({});
  const [imgError, setImgError]     = useState({});
  const [fading, setFading]         = useState(false);
  const imgRef = useRef();

  const count = photos.length;

  function changeIdx(newIdx) {
    if (newIdx === idx) return;
    setFading(true);
    setTimeout(() => {
      setIdx(newIdx);
      setZoom(1); setRotation(0); setPan({ x: 0, y: 0 });
      setFading(false);
    }, 120);
  }
  function prev() { changeIdx((idx - 1 + count) % count); }
  function next() { changeIdx((idx + 1) % count); }
  function resetZoom() { setZoom(1); setPan({ x: 0, y: 0 }); }
  function adjustZoom(delta) {
    setZoom((z) => Math.min(4, Math.max(1, +(z + delta).toFixed(1))));
    if (zoom + delta <= 1) setPan({ x: 0, y: 0 });
  }

  // Atajos de teclado — solo activos cuando el modal está abierto.
  useEffect(() => {
    function handleKey(e) {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.key === 'ArrowLeft')  { e.preventDefault(); prev(); }
      if (e.key === 'ArrowRight') { e.preventDefault(); next(); }
      if (e.key === '+' || e.key === '=') { e.preventDefault(); adjustZoom(0.5); }
      if (e.key === '-')          { e.preventDefault(); adjustZoom(-0.5); }
      if (e.key === '0')          { e.preventDefault(); resetZoom(); }
      if (e.key === 'f')          { e.preventDefault(); setFullscreen((v) => !v); }
      if (e.key === 'Escape')     { if (fullscreen) setFullscreen(false); else onClose && onClose(); }
      if (e.key === 'r')          { e.preventDefault(); setRotation((r) => (r + 90) % 360); }
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [idx, count, zoom, fullscreen]);

  function onMouseDown(e) {
    if (zoom <= 1) return;
    e.preventDefault();
    setDragging(true);
    setDragStart({ x: e.clientX, y: e.clientY });
    setPanStart({ ...pan });
  }
  function onMouseMove(e) {
    if (!dragging) return;
    setPan({ x: panStart.x + (e.clientX - dragStart.x), y: panStart.y + (e.clientY - dragStart.y) });
  }
  function onMouseUp() { setDragging(false); }

  const currentSrc = photos[idx];
  const loaded = imgLoaded[idx];
  const error = imgError[idx];

  const imgStyle = {
    maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', display: 'block',
    transform: `scale(${zoom}) translate(${pan.x / zoom}px, ${pan.y / zoom}px) rotate(${rotation}deg)`,
    transformOrigin: 'center center',
    transition: dragging ? 'none' : 'transform 0.2s cubic-bezier(0.25,0.1,0.25,1)',
    cursor: zoom > 1 ? (dragging ? 'grabbing' : 'grab') : 'zoom-in',
    opacity: fading ? 0 : 1,
    userSelect: 'none',
    borderRadius: 2,
  };

  const bgColor = embedded ? '#1a1f1d' : '#141918';

  const toolbarBtns = [
    { icon: 'zoom-in',    title: 'Zoom + (+)',     action: () => adjustZoom(0.5) },
    { icon: 'zoom-out',   title: 'Zoom - (-)',     action: () => adjustZoom(-0.5), disabled: zoom <= 1 },
    { icon: 'rotate-cw',  title: 'Rotar (R)',      action: () => setRotation((r) => (r + 90) % 360) },
    { icon: 'maximize-2', title: fullscreen ? 'Salir fullscreen (F)' : 'Pantalla completa (F)', action: () => setFullscreen((v) => !v) },
    { icon: 'download',   title: 'Descargar',      action: () => {
        const a = document.createElement('a');
        a.href = currentSrc;
        a.download = `parte-${parteId}-foto${idx + 1}.jpg`;
        a.click();
      } },
  ];

  const viewerContent = (
    <div
      style={{ flex: 1, position: 'relative', background: bgColor, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', userSelect: 'none', minHeight: 0 }}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={onMouseUp}
    >
      {count > 0 && (
        <div style={{ position: 'absolute', top: 10, left: 10, zIndex: 10, background: 'rgba(0,0,0,0.6)', color: 'white', fontSize: 11.5, fontWeight: 600, padding: '3px 8px', borderRadius: 4, fontFamily: "'JetBrains Mono', monospace", backdropFilter: 'blur(4px)' }}>
          {idx + 1} / {count}
        </div>
      )}
      {zoom > 1 && (
        <div style={{ position: 'absolute', top: 10, left: 60, zIndex: 10, background: 'rgba(58,158,110,0.85)', color: 'white', fontSize: 11, fontWeight: 700, padding: '3px 8px', borderRadius: 4, fontFamily: "'JetBrains Mono', monospace" }}>
          {zoom.toFixed(1)}×
        </div>
      )}
      <div style={{ position: 'absolute', top: 8, right: 8, zIndex: 10, display: 'flex', gap: 4 }}>
        {toolbarBtns.map((btn) => (
          <button
            key={btn.icon}
            title={btn.title}
            disabled={btn.disabled}
            onClick={btn.action}
            style={{
              width: 32, height: 32, border: 'none', borderRadius: 4,
              background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)',
              color: btn.disabled ? 'rgba(255,255,255,0.25)' : 'rgba(255,255,255,0.85)',
              cursor: btn.disabled ? 'default' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'background 0.1s',
            }}
            onMouseEnter={(e) => { if (!btn.disabled) e.currentTarget.style.background = 'rgba(58,158,110,0.7)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(0,0,0,0.55)'; }}
          >
            <Icon name={btn.icon} size={14} color="currentColor" />
          </button>
        ))}
      </div>

      {count > 1 && (
        <button
          onClick={prev}
          style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', zIndex: 10, width: 36, height: 36, borderRadius: '50%', border: 'none', background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)', color: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: 0.7, transition: 'opacity 0.1s' }}
          onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
          onMouseLeave={(e) => (e.currentTarget.style.opacity = '0.7')}
        >
          <Icon name="chevron-left" size={18} color="white" />
        </button>
      )}
      {count > 1 && (
        <button
          onClick={next}
          style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', zIndex: 10, width: 36, height: 36, borderRadius: '50%', border: 'none', background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)', color: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: 0.7, transition: 'opacity 0.1s' }}
          onMouseEnter={(e) => (e.currentTarget.style.opacity = '1')}
          onMouseLeave={(e) => (e.currentTarget.style.opacity = '0.7')}
        >
          <Icon name="chevron-right" size={18} color="white" />
        </button>
      )}

      <div style={{ flex: 1, width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', position: 'relative', padding: '12px 50px' }}>
        {!loaded && !error && count > 0 && (
          <div className="skeleton" style={{ position: 'absolute', inset: 0, margin: 12, borderRadius: 4 }} />
        )}
        {count === 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, color: 'rgba(255,255,255,0.4)' }}>
            <Icon name="slash" size={48} color="rgba(255,255,255,0.2)" />
            <div style={{ fontSize: 14, fontWeight: 500 }}>Este parte no tiene imágenes</div>
            <div style={{ fontSize: 12, opacity: 0.6 }}>El operario no cargó fotos en la app móvil</div>
          </div>
        )}
        {error && count > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10, color: 'rgba(255,255,255,0.5)' }}>
            <Icon name="alert-triangle" size={36} color="rgba(192,57,43,0.7)" />
            <div style={{ fontSize: 13 }}>No se pudo cargar la imagen</div>
            <button
              onClick={() => setImgError((e) => ({ ...e, [idx]: false }))}
              style={{ padding: '5px 12px', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 4, background: 'transparent', color: 'rgba(255,255,255,0.7)', fontSize: 12, cursor: 'pointer' }}
            >
              Reintentar
            </button>
          </div>
        )}
        {count > 0 && !error && (
          <img
            ref={imgRef}
            key={`${idx}-${currentSrc}`}
            src={currentSrc}
            alt={`Foto ${idx + 1} de ${count} del parte ${parteId}`}
            style={{ ...imgStyle, maxHeight: embedded ? 380 : '100%' }}
            onLoad={() => setImgLoaded((l) => ({ ...l, [idx]: true }))}
            onError={() => setImgError((e) => ({ ...e, [idx]: true }))}
            onMouseDown={onMouseDown}
            draggable={false}
          />
        )}
      </div>

      {count > 1 && (
        <ThumbnailStrip photos={photos} activeIdx={idx} onSelect={changeIdx} size={embedded ? 52 : 64} />
      )}
    </div>
  );

  if (fullscreen) {
    return (
      <div
        style={{ position: 'fixed', inset: 0, background: '#0a0d0c', zIndex: 9999, display: 'flex', flexDirection: 'column' }}
        role="dialog"
        aria-modal="true"
        aria-label={`Visor de fotos — parte ${parteId}`}
      >
        <div style={{ padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 10, background: 'rgba(0,0,0,0.4)' }}>
          <span style={{ color: 'rgba(255,255,255,0.7)', fontSize: 12, fontFamily: "'JetBrains Mono', monospace" }}>
            Parte {parteId} · Foto {idx + 1}/{count}
          </span>
          <div style={{ flex: 1 }} />
          <button
            onClick={() => setFullscreen(false)}
            style={{ padding: '5px 12px', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 4, background: 'transparent', color: 'rgba(255,255,255,0.7)', fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <Icon name="minimize-2" size={13} color="currentColor" /> Salir (F / Esc)
          </button>
        </div>
        {viewerContent}
      </div>
    );
  }

  return viewerContent;
}

// ── Panel lateral del modal — datos del parte ────────────────────
function ModalDetailPanel({ parte, onGoToDetalle, obsOverride }) {
  const p = parte || {};
  const obs = obsOverride || getMockObs(p.id || '0');
  const allNo = Object.values(obs).every((v) => !v);
  const tc = TRAZA_CONFIG[p.traza] || {};

  const pS = {
    panel: { width: 340, minWidth: 300, background: 'white', borderLeft: '1px solid #eaeeec', display: 'flex', flexDirection: 'column', overflow: 'hidden' },
    header: { padding: '12px 16px', borderBottom: '1px solid #eaeeec', background: '#fafcfb' },
    parteId: { fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700, color: '#124e2f' },
    body: { flex: 1, overflowY: 'auto', padding: 0 },
    section: { padding: '12px 16px', borderBottom: '1px solid #f0f3f1' },
    sectionLabel: { fontSize: 10, fontWeight: 700, color: '#8f9c97', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 },
    field: { marginBottom: 8 },
    fieldLabel: { fontSize: 10.5, fontWeight: 600, color: '#6b7772', marginBottom: 2 },
    fieldVal: { fontSize: 13.5, fontWeight: 600, color: '#111614', fontFamily: "'JetBrains Mono', monospace" },
    fieldValNormal: { fontSize: 12.5, fontWeight: 500, color: '#2f3733' },
    medRow: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 },
    medBadge: { padding: '2px 7px', borderRadius: 3, fontSize: 10, fontWeight: 700, letterSpacing: '0.04em' },
    medVal: { fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: '#2f3733' },
    obsGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 8px' },
    obsItem: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '4px 0' },
    obsLabel: { fontSize: 11, color: '#4a5550', display: 'flex', alignItems: 'center', gap: 5 },
    obsChip: { padding: '1px 7px', borderRadius: 10, fontSize: 10, fontWeight: 600 },
    footer: { padding: '12px 16px', borderTop: '1px solid #eaeeec', display: 'flex', flexDirection: 'column', gap: 7 },
    btnSecondary: { padding: 7, border: '1px solid #d5ddd9', borderRadius: 4, background: 'white', color: '#4a5550', fontSize: 12, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 },
    btnSuccess: { padding: 6, border: 'none', borderRadius: 4, background: '#1d8348', color: 'white', fontSize: 11.5, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5 },
  };

  return (
    <div style={pS.panel}>
      <div style={pS.header}>
        <div style={pS.parteId}>{p.id || 'PD-2025-00042'}</div>
        <div style={{ marginTop: 4, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <StatusChip label={p.traza || 'Error Sumi Nro Med'} config={tc} size="xs" />
          <StatusChip label={p.estado || 'En Revisión'} config={PARTE_ESTADO_CONFIG[p.estado] || {}} size="xs" />
        </div>
      </div>
      <div style={pS.body}>
        <div style={pS.section}>
          <div style={pS.sectionLabel}>Identificación</div>
          <div style={pS.field}>
            <div style={pS.fieldLabel}>Suministro</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={pS.fieldVal}>{p.suministro || '412881'}</span>
              <button title="Copiar" style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#8f9c97', padding: 2 }}>
                <Icon name="link" size={12} color="#b5bfbb" />
              </button>
            </div>
          </div>
          <div style={pS.field}>
            <div style={pS.fieldLabel}>Fecha ejecución</div>
            <div style={pS.fieldValNormal}>{p.fecha || '01/04/2025'}</div>
          </div>
          <div style={pS.field}>
            <div style={pS.fieldLabel}>Operario</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <div style={{ width: 22, height: 22, borderRadius: '50%', background: '#edf5f0', color: '#124e2f', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700 }}>
                {(p.operario || 'LM').split(',')[0]?.charAt(0)}
                {(p.operario || 'LM').split(' ').pop()?.charAt(0)}
              </div>
              <span style={pS.fieldValNormal}>{p.operario || 'López, M.'}</span>
            </div>
          </div>
          <div style={pS.field}>
            <div style={pS.fieldLabel}>Contratista</div>
            <span style={{ fontSize: 11, fontWeight: 700, padding: '2px 7px', borderRadius: 3, background: (p.contratista || 'CONECTAR') === 'CONECTAR' ? '#edf5f0' : '#dbeafe', color: (p.contratista || 'CONECTAR') === 'CONECTAR' ? '#124e2f' : '#0d4272' }}>
              {p.contratista || 'CONECTAR'}
            </span>
          </div>
        </div>

        <div style={pS.section}>
          <div style={pS.sectionLabel}>Medidores</div>
          <div style={pS.medRow}>
            <span style={{ ...pS.medBadge, background: '#fde8e8', color: '#7a1c1c' }}>RETIRADO</span>
            <span style={pS.medVal}>M{parseInt((p.medidor_dec || 'M74829103').slice(1)) - 1000}</span>
          </div>
          <div style={{ paddingLeft: 16, marginBottom: 4 }}>
            <Icon name="chevron-down" size={13} color="#b5bfbb" />
          </div>
          <div style={pS.medRow}>
            <span style={{ ...pS.medBadge, background: '#d4edda', color: '#155a2e' }}>COLOCADO</span>
            <span style={pS.medVal}>{p.medidor_dec || 'M74829103'}</span>
          </div>
        </div>

        <div style={pS.section}>
          <div style={pS.sectionLabel}>Observaciones — App Móvil</div>
          {allNo && (
            <div style={{ padding: '6px 8px', background: '#f5f7f6', borderRadius: 4, fontSize: 11, color: '#6b7772', marginBottom: 8 }}>
              Sin observaciones cargadas en app móvil
            </div>
          )}
          <div style={pS.obsGrid}>
            {OBSERVACIONES_LABELS.map((o) => {
              const val = obs[o.key];
              return (
                <div key={o.key} style={pS.obsItem}>
                  <span style={pS.obsLabel}>
                    <Icon name={o.icon} size={11} color="#b5bfbb" />
                    {o.label}
                  </span>
                  <span
                    style={{
                      ...pS.obsChip,
                      background: val ? '#d4edda' : '#f0f3f1',
                      color: val ? '#155a2e' : '#8f9c97',
                    }}
                  >
                    {val ? 'Sí' : 'No'}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div style={pS.footer}>
        <div style={{ display: 'flex', gap: 6 }}>
          <button style={{ ...pS.btnSuccess, flex: 1 }}>
            <Icon name="check-circle" size={13} /> Aprobar
          </button>
          <button style={{ ...pS.btnSecondary, flex: 1, fontSize: 11 }}>
            <Icon name="clock" size={13} /> Revisión
          </button>
        </div>
        <button style={pS.btnSecondary} onClick={onGoToDetalle}>
          <Icon name="edit" size={13} /> Ir al detalle completo
        </button>
      </div>
    </div>
  );
}

// ── Modal completo (B5 — icono cámara en bandeja) ─────────────────
export function VisorModal({ parte, onClose, onGoToDetalle }) {
  const [photos, setPhotos] = useState(() => getPartePhotos(parte?.id));
  const [obsOverride, setObsOverride] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    if (parte?._id) {
      getVisor(parte._id)
        .then((data) => {
          if (cancelled) return;
          setPhotos((data.imagenes || []).map((img) => img.url));
          setObsOverride(mapApiObs(data.observaciones_app));
          setLoading(false);
        })
        .catch(() => {
          if (cancelled) return;
          setPhotos(getPartePhotos(parte?.id));
          setObsOverride(null);
          setLoading(false);
        });
    } else {
      const t = setTimeout(() => {
        if (!cancelled) {
          setPhotos(getPartePhotos(parte?.id));
          setLoading(false);
        }
      }, 300);
      return () => { cancelled = true; clearTimeout(t); };
    }
    return () => { cancelled = true; };
  }, [parte?._id, parte?.id]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Visor de imágenes — ${parte?.id}`}
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.72)', zIndex: 500, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        style={{
          width: 'min(1380px, 90vw)',
          height: 'min(900px, 90vh)',
          background: '#1a1f1d',
          borderRadius: 8,
          overflow: 'hidden',
          boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
          display: 'flex',
          flexDirection: 'column',
          animation: 'modalIn 0.18s cubic-bezier(0.25,0.1,0.25,1)',
        }}
      >
        <div style={{ padding: '10px 14px', background: '#111614', borderBottom: '1px solid rgba(255,255,255,0.07)', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <Icon name="camera" size={15} color="#6dbf97" />
          <span style={{ color: 'white', fontSize: 13, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>{parte?.id}</span>
          <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: 12, marginLeft: 2 }}>— Suministro {parte?.suministro}</span>
          <div style={{ flex: 1 }} />
          <span style={{ color: 'rgba(255,255,255,0.35)', fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}>
            {photos.length} foto{photos.length !== 1 ? 's' : ''}
          </span>
          <button
            onClick={onClose}
            style={{ border: 'none', background: 'rgba(255,255,255,0.07)', borderRadius: 4, cursor: 'pointer', color: 'rgba(255,255,255,0.6)', width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'background 0.1s' }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.15)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.07)')}
          >
            <Icon name="x" size={15} color="currentColor" />
          </button>
        </div>

        <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          {loading ? (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div className="skeleton" style={{ width: '60%', height: '80%', borderRadius: 4, background: 'rgba(255,255,255,0.05)' }} />
            </div>
          ) : (
            <ImageViewer photos={photos} parteId={parte?.id} onClose={onClose} />
          )}
          <ModalDetailPanel parte={parte} onGoToDetalle={onGoToDetalle} obsOverride={obsOverride} />
        </div>

        <div style={{ padding: '5px 14px', background: '#111614', borderTop: '1px solid rgba(255,255,255,0.05)', display: 'flex', gap: 16, flexShrink: 0 }}>
          {[['← →', 'Navegar'], ['+ −', 'Zoom'], ['0', 'Reset'], ['R', 'Rotar'], ['F', 'Pantalla completa'], ['Esc', 'Cerrar']].map(([k, l]) => (
            <span key={k} style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)', display: 'flex', gap: 5 }}>
              <kbd style={{ background: 'rgba(255,255,255,0.08)', padding: '1px 5px', borderRadius: 3, fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: 'rgba(255,255,255,0.45)' }}>
                {k}
              </kbd>
              {l}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Visor embebido para B6 (Detalle) ──────────────────────────────
export function EmbeddedVisor({ parte }) {
  const [photos, setPhotos] = useState(() => getPartePhotos(parte?.id));

  useEffect(() => {
    let cancelled = false;
    if (parte?._id) {
      getVisor(parte._id)
        .then((data) => {
          if (!cancelled) setPhotos((data.imagenes || []).map((img) => img.url));
        })
        .catch(() => {
          if (!cancelled) setPhotos(getPartePhotos(parte?.id));
        });
    } else {
      setPhotos(getPartePhotos(parte?.id));
    }
    return () => { cancelled = true; };
  }, [parte?._id, parte?.id]);

  return (
    <div style={{ background: '#1a1f1d', borderRadius: 6, overflow: 'hidden', height: 440, display: 'flex' }}>
      <ImageViewer photos={photos} parteId={parte?.id} embedded onClose={() => {}} />
    </div>
  );
}
