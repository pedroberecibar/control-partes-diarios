import { useEffect, useRef, useState } from 'react';
import { Icon } from '../components/Icon';
import { ProgressBar } from '../components/ProgressBar';
import { crearLote, getLote, previewColumnas } from '../api/lotesApi';

// Temporary mapping — must match seeded contratista IDs in the DB.
// If they differ, update these values after checking `SELECT id, nombre FROM contratistas`.
const CONTRATISTA_IDS = { CONECTAR: 1, COOPLYF: 2 };
const USUARIO_ID_DEFAULT = 1; // hardcoded until auth context is wired

const PREVIEW_ROWS = [
  { sumi: '412881', operario: 'García J.',     fecha: '01/04/2025', med_ret: 'M74829103', med_col: 'M74829200', cod_epec: '1003', ord_nro: 'CE-482301', obs: 'Cambio prog.' },
  { sumi: '518204', operario: 'López M.',      fecha: '01/04/2025', med_ret: 'M61024877', med_col: 'M61025000', cod_epec: '1004', ord_nro: 'CE-517822', obs: '' },
  { sumi: '623771', operario: 'Fernández A.',  fecha: '01/04/2025', med_ret: 'M80112340', med_col: 'M80112500', cod_epec: '1003', ord_nro: '',          obs: 'Sin orden asig' },
  { sumi: '704412', operario: 'García J.',     fecha: '01/04/2025', med_ret: 'M55019980', med_col: 'M55020100', cod_epec: '2001', ord_nro: 'CE-600110', obs: '' },
  { sumi: '811093', operario: 'Torres R.',     fecha: '01/04/2025', med_ret: 'M90231177', med_col: 'M90231300', cod_epec: '1002', ord_nro: 'CE-711209', obs: '' },
];

export function SubidaArchivos({ onBack }) {
  const [dragOver, setDragOver]               = useState(false);
  const [files, setFiles]                     = useState([]);
  const [contratista, setContratista]         = useState('CONECTAR');
  const [step, setStep]                       = useState('drop'); // drop | preview | mapping | uploading | result | error
  const [uploadResult, setUploadResult]       = useState(null);
  const [uploadError, setUploadError]         = useState(null);
  const [errorPayload, setErrorPayload]       = useState(null); // { code, lote_existente_id?, ... }
  const [overlapWarn, setOverlapWarn]         = useState(null); // { overlap_pct, n_existentes, n_total }
  const [progressLote, setProgressLote]       = useState(null); // último snapshot del lote para barra
  // Mapeo de columnas
  const [columnasPreview, setColumnasPreview] = useState(null);  // respuesta de preview-columnas
  const [mapeoSel, setMapeoSel]               = useState({});    // {campo_canonico: col_excel}
  const [loadingPreview, setLoadingPreview]   = useState(false);
  const fileInputRef = useRef();
  const pollRef = useRef(null);

  function handleDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const dropped = Array.from(e.dataTransfer.files).filter((f) => f.name.match(/\.(xlsx|xls|csv)$/i));
    if (dropped.length) { setFiles(dropped); setStep('preview'); }
  }
  function handleFileInput(e) {
    const chosen = Array.from(e.target.files).filter((f) => f.name.match(/\.(xlsx|xls|csv)$/i));
    if (chosen.length) { setFiles(chosen); setStep('preview'); }
  }

  async function goToMapping() {
    if (!files.length) return;
    setLoadingPreview(true);
    try {
      const resultado = await previewColumnas(files[0], CONTRATISTA_IDS[contratista] ?? 1);
      setColumnasPreview(resultado);
      // Pre-seleccionar el mapeo sugerido: invertir {col_excel: canonico} → {canonico: col_excel}
      const presel = {};
      for (const [col, canonico] of Object.entries(resultado.mapeo_sugerido || {})) {
        if (!presel[canonico]) presel[canonico] = col;
      }
      setMapeoSel(presel);
      setStep('mapping');
    } catch (err) {
      setUploadError(err.message || 'Error al detectar columnas.');
      setStep('error');
    } finally {
      setLoadingPreview(false);
    }
  }

  async function doUpload({ force = false, mapeo = null } = {}) {
    if (!files.length) return;
    setStep('uploading');
    setUploadResult(null);
    setUploadError(null);
    setErrorPayload(null);
    setOverlapWarn(null);
    setProgressLote(null);
    try {
      const lote = await crearLote(
        files[0],
        CONTRATISTA_IDS[contratista] ?? 1,
        USUARIO_ID_DEFAULT,
        { force, mapeo },
      );
      setUploadResult(lote);
      setProgressLote(lote);
      setStep('result');
    } catch (err) {
      if (err.code === 'OVERLAP_WARN') {
        setOverlapWarn(err.payload || null);
        setStep('mapping'); // volver a mapping con el modal abierto encima
      } else {
        setErrorPayload(err.payload || null);
        setUploadError(err.message || 'Error desconocido al subir el archivo.');
        setStep('error');
      }
    }
  }

  function buildMapeoParaEnviar() {
    // Invierte mapeoSel {canonico: col_excel} → {col_excel: canonico}
    const out = {};
    for (const [canonico, col] of Object.entries(mapeoSel)) {
      if (col && col !== '__none__') out[col] = canonico;
    }
    return Object.keys(out).length ? out : null;
  }

  const handleUpload = () => doUpload({ force: false, mapeo: buildMapeoParaEnviar() });
  const handleUploadForce = () => doUpload({ force: true, mapeo: buildMapeoParaEnviar() });

  // Polling de progreso del lote recién creado mientras el worker procesa.
  useEffect(() => {
    if (step !== 'result' || !progressLote?.id) return;
    const inProgress = ['RECIBIDO', 'PROCESANDO'].includes(progressLote.estado);
    if (!inProgress) return;
    pollRef.current = setTimeout(() => {
      getLote(progressLote.id)
        .then((fresh) => setProgressLote(fresh))
        .catch(() => {});
    }, 2000);
    return () => clearTimeout(pollRef.current);
  }, [step, progressLote]);

  function resetFlow() {
    clearTimeout(pollRef.current);
    setFiles([]);
    setUploadResult(null);
    setUploadError(null);
    setErrorPayload(null);
    setOverlapWarn(null);
    setProgressLote(null);
    setColumnasPreview(null);
    setMapeoSel({});
    setStep('drop');
  }

  const sS = {
    root: { padding: 20, overflow: 'auto', height: '100%', boxSizing: 'border-box' },
    pageHeader: { display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 },
    backBtn: { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 10px', border: '1px solid #d5ddd9', borderRadius: 4, background: 'white', fontSize: 12, fontWeight: 600, color: '#4a5550', cursor: 'pointer' },
    pageTitle: { fontSize: 17, fontWeight: 700, color: '#111614' },
    pageSub: { fontSize: 12, color: '#8f9c97', marginTop: 2 },
    card: { background: 'white', border: '1px solid #eaeeec', borderRadius: 6, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', marginBottom: 16 },
    cardHeader: { padding: '10px 16px', borderBottom: '1px solid #eaeeec', background: '#fafcfb', display: 'flex', alignItems: 'center', gap: 8 },
    cardTitle: { fontSize: 12, fontWeight: 700, color: '#2f3733', flex: 1 },
    cardBody: { padding: 16 },
    dropZone: {
      border: `2px dashed ${dragOver ? '#124e2f' : '#d5ddd9'}`,
      borderRadius: 6,
      padding: '40px 24px',
      textAlign: 'center',
      background: dragOver ? '#edf5f0' : '#fafcfb',
      transition: 'all 0.15s',
      cursor: 'pointer',
    },
    dropIcon: { marginBottom: 12 },
    dropTitle: { fontSize: 14, fontWeight: 600, color: dragOver ? '#124e2f' : '#4a5550', marginBottom: 6 },
    dropSub: { fontSize: 12, color: '#8f9c97' },
    selectorRow: { display: 'flex', gap: 10, alignItems: 'center', marginBottom: 16 },
    selectorLabel: { fontSize: 12.5, fontWeight: 600, color: '#2f3733', minWidth: 80 },
    selectorBtns: { display: 'flex', gap: 6 },
    selectorBtn: { padding: '6px 14px', border: '1px solid #d5ddd9', borderRadius: 4, fontSize: 12, fontWeight: 600, cursor: 'pointer', transition: 'all 0.12s', color: '#4a5550', background: 'white' },
    selectorBtnActive: { background: '#124e2f', color: 'white', borderColor: '#124e2f' },
    table: { width: '100%', borderCollapse: 'collapse', fontSize: 11.5 },
    th: { padding: '7px 10px', textAlign: 'left', background: '#124e2f', color: 'white', fontWeight: 600, fontSize: 10.5, letterSpacing: '0.04em', whiteSpace: 'nowrap' },
    td: { padding: '6px 10px', borderBottom: '1px solid #f0f3f1', color: '#2f3733', whiteSpace: 'nowrap', fontFamily: "'JetBrains Mono', monospace" },
    fileChip: { display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 12px', background: '#edf5f0', border: '1px solid #a8d9c0', borderRadius: 4, fontSize: 12, color: '#124e2f', fontWeight: 500 },
    btnPrimary: { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 18px', border: 'none', borderRadius: 4, background: '#124e2f', fontSize: 12.5, fontWeight: 600, color: 'white', cursor: 'pointer' },
    btnSecondary: { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 14px', border: '1px solid #d5ddd9', borderRadius: 4, background: 'white', fontSize: 12.5, fontWeight: 600, color: '#4a5550', cursor: 'pointer' },
    mono: { fontFamily: "'JetBrains Mono', monospace" },
  };

  return (
    <div style={sS.root}>
      <div style={sS.pageHeader}>
        <button style={sS.backBtn} onClick={onBack}>
          <Icon name="arrow-left" size={13} /> Volver
        </button>
        <div>
          <div style={sS.pageTitle}>Subir Archivos de Partes</div>
          <div style={sS.pageSub}>Módulo A — Ingesta por Drag & Drop</div>
        </div>
      </div>

      {/* ── Step: selección de archivo ────────────────────────── */}
      {step === 'drop' && (
        <div style={sS.card}>
          <div style={sS.cardBody}>
            <div style={sS.selectorRow}>
              <span style={sS.selectorLabel}>Contratista</span>
              <div style={sS.selectorBtns}>
                {['CONECTAR', 'COOPLYF'].map((c) => (
                  <button
                    key={c}
                    style={{ ...sS.selectorBtn, ...(contratista === c ? sS.selectorBtnActive : {}) }}
                    onClick={() => setContratista(c)}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>
            <div
              style={sS.dropZone}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx,.xls,.csv"
                multiple
                style={{ display: 'none' }}
                onChange={handleFileInput}
              />
              <div style={sS.dropIcon}>
                <Icon name="file-up" size={36} color={dragOver ? '#124e2f' : '#b5bfbb'} />
              </div>
              <div style={sS.dropTitle}>
                {dragOver ? 'Soltar archivos aquí' : 'Arrastrá archivos o hacé click para seleccionar'}
              </div>
              <div style={sS.dropSub}>.xlsx · .xls · .csv · Hasta 50 MB por archivo · Múltiples archivos permitidos</div>
            </div>
          </div>
        </div>
      )}

      {/* ── Step: vista previa ────────────────────────────────── */}
      {step === 'preview' && (
        <>
          <div style={sS.card}>
            <div style={sS.cardHeader}>
              <Icon name="file-text" size={14} color="#6b7772" />
              <span style={sS.cardTitle}>Archivos seleccionados</span>
              <button style={{ ...sS.btnSecondary, fontSize: 11 }} onClick={resetFlow}>Cambiar</button>
            </div>
            <div style={sS.cardBody}>
              <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
                {files.map((f, i) => (
                  <div key={i} style={sS.fileChip}>
                    <Icon name="file-text" size={13} color="#124e2f" />
                    {f.name}
                    <span style={{ color: '#8f9c97', fontWeight: 400, fontSize: 11 }}>({(f.size / 1024).toFixed(0)} KB)</span>
                  </div>
                ))}
              </div>
              <div style={{ ...sS.selectorRow, marginBottom: 0 }}>
                <span style={sS.selectorLabel}>Contratista</span>
                <div style={sS.selectorBtns}>
                  {['CONECTAR', 'COOPLYF'].map((c) => (
                    <button
                      key={c}
                      style={{ ...sS.selectorBtn, ...(contratista === c ? sS.selectorBtnActive : {}) }}
                      onClick={() => setContratista(c)}
                    >
                      {c}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div style={sS.card}>
            <div style={sS.cardHeader}>
              <Icon name="eye" size={14} color="#6b7772" />
              <span style={sS.cardTitle}>Vista previa — primeras 5 filas (referencia)</span>
              <span style={{ fontSize: 10.5, color: '#8f9c97' }}>Solo lectura</span>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table style={sS.table}>
                <thead>
                  <tr>
                    {['SUMINISTRO', 'OPERARIO', 'FECHA_PARTE', 'MED_RETIRADO', 'MED_COLOCADO', 'COD_EPEC', 'ORD_NRO', 'OBS_APP'].map((h) => (
                      <th key={h} style={sS.th}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {PREVIEW_ROWS.map((r, i) => (
                    <tr key={i} style={{ background: i % 2 === 0 ? 'white' : '#fafcfb' }}>
                      <td style={sS.td}>{r.sumi}</td>
                      <td style={{ ...sS.td, fontFamily: 'inherit' }}>{r.operario}</td>
                      <td style={sS.td}>{r.fecha}</td>
                      <td style={sS.td}>{r.med_ret}</td>
                      <td style={sS.td}>{r.med_col}</td>
                      <td style={sS.td}>{r.cod_epec}</td>
                      <td style={{ ...sS.td, color: r.ord_nro ? '#2f3733' : '#c0392b', fontWeight: r.ord_nro ? 400 : 600 }}>
                        {r.ord_nro || '(vacío)'}
                      </td>
                      <td style={{ ...sS.td, fontFamily: 'inherit' }}>{r.obs || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
            <button style={sS.btnSecondary} onClick={resetFlow}>Cancelar</button>
            <button style={sS.btnPrimary} onClick={goToMapping} disabled={loadingPreview}>
              {loadingPreview
                ? <><Icon name="loader" size={13} /> Detectando columnas…</>
                : <><Icon name="arrow-right" size={14} /> Siguiente: Mapeo de columnas</>}
            </button>
          </div>
        </>
      )}

      {/* ── Step: mapeo de columnas ──────────────────────────── */}
      {step === 'mapping' && columnasPreview && (
        <>
          <div style={sS.card}>
            <div style={sS.cardHeader}>
              <Icon name="sliders" size={14} color="#6b7772" />
              <span style={sS.cardTitle}>Mapeo de columnas — {files[0]?.name}</span>
              <span style={{ fontSize: 10.5, color: '#8f9c97' }}>Confirmar o ajustar</span>
            </div>
            <div style={sS.cardBody}>
              <p style={{ fontSize: 12, color: '#6b7772', marginBottom: 12, marginTop: 0 }}>
                Se detectaron <strong>{columnasPreview.columnas_detectadas.length}</strong> columnas en el archivo.
                Asigná cada campo del sistema a la columna que le corresponde.
              </p>
              <table style={{ ...sS.table, marginBottom: 0 }}>
                <thead>
                  <tr>
                    <th style={sS.th}>Campo del sistema</th>
                    <th style={sS.th}>Columna del archivo</th>
                  </tr>
                </thead>
                <tbody>
                  {columnasPreview.campos_canonicos.map((campo) => {
                    const requerido = campo.requerido;
                    const valorSel = mapeoSel[campo.nombre] || '__none__';
                    const sinMapear = requerido && valorSel === '__none__';
                    return (
                      <tr key={campo.nombre}>
                        <td style={{ ...sS.td, fontFamily: 'inherit' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span style={{ fontWeight: 600, color: '#2f3733' }}>{campo.nombre}</span>
                            {requerido
                              ? <span style={{ fontSize: 9, padding: '1px 5px', background: '#c0392b', color: 'white', borderRadius: 3, fontWeight: 700, letterSpacing: '0.05em' }}>REQ</span>
                              : <span style={{ fontSize: 9, padding: '1px 5px', background: '#d5ddd9', color: '#6b7772', borderRadius: 3, fontWeight: 600 }}>OPT</span>}
                          </div>
                          <div style={{ fontSize: 10.5, color: '#8f9c97', marginTop: 1 }}>{campo.descripcion}</div>
                        </td>
                        <td style={sS.td}>
                          <select
                            value={valorSel}
                            onChange={(e) => setMapeoSel((prev) => ({ ...prev, [campo.nombre]: e.target.value }))}
                            style={{
                              width: '100%', padding: '5px 8px', border: `1px solid ${sinMapear ? '#c0392b' : '#d5ddd9'}`,
                              borderRadius: 4, fontSize: 12, background: sinMapear ? '#fff5f5' : 'white', color: '#2f3733',
                            }}
                          >
                            <option value="__none__">— No mapear —</option>
                            {columnasPreview.columnas_detectadas.map((col) => (
                              <option key={col} value={col}>{col}</option>
                            ))}
                          </select>
                          {sinMapear && (
                            <div style={{ fontSize: 10.5, color: '#c0392b', marginTop: 2 }}>Campo requerido — debe estar mapeado</div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
            <button style={sS.btnSecondary} onClick={() => setStep('preview')}>
              <Icon name="arrow-left" size={13} /> Volver
            </button>
            <button
              style={{
                ...sS.btnPrimary,
                opacity: columnasPreview.campos_canonicos.filter((c) => c.requerido && (!mapeoSel[c.nombre] || mapeoSel[c.nombre] === '__none__')).length ? 0.5 : 1,
                cursor: columnasPreview.campos_canonicos.filter((c) => c.requerido && (!mapeoSel[c.nombre] || mapeoSel[c.nombre] === '__none__')).length ? 'not-allowed' : 'pointer',
              }}
              disabled={columnasPreview.campos_canonicos.some((c) => c.requerido && (!mapeoSel[c.nombre] || mapeoSel[c.nombre] === '__none__'))}
              onClick={handleUpload}
            >
              <Icon name="upload" size={14} /> Procesar lote
            </button>
          </div>
        </>
      )}

      {/* ── Step: subiendo ───────────────────────────────────── */}
      {step === 'uploading' && (
        <div style={sS.card}>
          <div style={sS.cardBody}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14 }}>
              <Icon name="loader" size={22} color="#124e2f" />
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#2f3733' }}>
                  Subiendo {files[0]?.name}…
                </div>
                <div style={{ fontSize: 11.5, color: '#8f9c97', marginTop: 3 }}>
                  Enviando al backend · Contratista: {contratista}
                </div>
              </div>
            </div>
            <ProgressBar pct={5} paso="RECIBIENDO" estado="PROCESANDO" size="md" />
          </div>
        </div>
      )}

      {/* ── Step: resultado exitoso ───────────────────────────── */}
      {step === 'result' && uploadResult && (
        <>
          <div style={{ ...sS.card, border: '1px solid #a8d9c0' }}>
            <div style={{ ...sS.cardHeader, background: '#edf5f0', borderBottom: '1px solid #a8d9c0' }}>
              <Icon name="check-circle" size={14} color="#1d8348" />
              <span style={{ ...sS.cardTitle, color: '#155a2e' }}>
                Lote creado — procesamiento iniciado en background
              </span>
            </div>
            <div style={sS.cardBody}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12, marginBottom: 14 }}>
                {[
                  ['ID Lote', `#${uploadResult.id}`],
                  ['Archivo', uploadResult.nombre_archivo],
                  ['Estado', progressLote?.estado || uploadResult.estado],
                ].map(([l, v]) => (
                  <div key={l}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: '#8f9c97', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>{l}</div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#111614', ...sS.mono }}>{v}</div>
                  </div>
                ))}
              </div>
              <ProgressBar
                pct={progressLote?.progreso_pct ?? 0}
                paso={progressLote?.paso_actual}
                estado={progressLote?.estado === 'APROBADO'
                  ? 'APROBADO'
                  : progressLote?.estado === 'RECHAZADO'
                    ? 'RECHAZADO'
                    : 'PROCESANDO'}
                size="md"
              />
              {progressLote?.estado === 'RECHAZADO' && progressLote?.detalle_error && (
                <div style={{ marginTop: 10, padding: '8px 12px', background: '#fde8e8', border: '1px solid #f5b7b1', borderRadius: 4, fontSize: 11.5, color: '#7a1c1c', fontFamily: "'JetBrains Mono', monospace" }}>
                  {progressLote.detalle_error}
                </div>
              )}
            </div>
          </div>

          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
            <button style={sS.btnSecondary} onClick={resetFlow}>
              <Icon name="upload" size={13} /> Subir otro archivo
            </button>
            <button style={sS.btnPrimary} onClick={onBack}>
              <Icon name="list" size={13} /> Ver Lista de Lotes
            </button>
          </div>
        </>
      )}

      {/* ── Step: error ───────────────────────────────────────── */}
      {step === 'error' && (
        <>
          <div style={{ ...sS.card, border: '1px solid #f5b7b1' }}>
            <div style={{ ...sS.cardHeader, background: '#fde8e8', borderBottom: '1px solid #f5b7b1' }}>
              <Icon name="x-circle" size={14} color="#c0392b" />
              <span style={{ ...sS.cardTitle, color: '#7a1c1c' }}>
                {errorPayload?.code === 'DUP_BYTES' && 'Archivo idéntico ya subido'}
                {errorPayload?.code === 'DUP_CONTENT' && 'El contenido ya fue procesado en otro lote'}
                {!['DUP_BYTES', 'DUP_CONTENT'].includes(errorPayload?.code) && 'Error al subir el archivo'}
              </span>
            </div>
            <div style={sS.cardBody}>
              <div style={{ padding: '10px 12px', background: '#fde8e8', borderRadius: 4, fontSize: 12.5, color: '#7a1c1c', fontFamily: "'JetBrains Mono', monospace" }}>
                {uploadError}
              </div>
              {errorPayload?.lote_existente_id ? (
                <div style={{ marginTop: 10, fontSize: 12, color: '#4a5550' }}>
                  Lote existente: <strong>#{errorPayload.lote_existente_id}</strong>. Si querés reprocesarlo, abrí la Lista de Lotes y usá la acción "Reprocesar".
                </div>
              ) : (
                <div style={{ marginTop: 10, fontSize: 11.5, color: '#6b7772' }}>
                  Verificá que el backend esté corriendo en <code>http://localhost:8000</code> y que el contratista ID {CONTRATISTA_IDS[contratista]} exista en la base de datos.
                </div>
              )}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
            <button style={sS.btnSecondary} onClick={resetFlow}>Volver a intentar</button>
          </div>
        </>
      )}

      {/* ── Modal: confirmación overlap ─────────────────────── */}
      {overlapWarn && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed', inset: 0,
            background: 'rgba(17,22,20,0.45)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 1000,
          }}
          onClick={() => setOverlapWarn(null)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: 'white', borderRadius: 8, width: 460, maxWidth: '92%',
              boxShadow: '0 10px 40px rgba(0,0,0,0.18)',
              animation: 'modalIn 0.18s ease',
              overflow: 'hidden',
            }}
          >
            <div style={{ padding: '14px 18px', background: '#fff3cd', borderBottom: '1px solid #f5d56a', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Icon name="alert-circle" size={16} color="#7a4a00" />
              <span style={{ fontSize: 13, fontWeight: 700, color: '#7a4a00' }}>
                Posible duplicado parcial
              </span>
            </div>
            <div style={{ padding: '16px 18px' }}>
              <p style={{ fontSize: 13, color: '#2f3733', margin: 0, lineHeight: 1.5 }}>
                <strong>{overlapWarn.n_existentes}</strong> de <strong>{overlapWarn.n_total}</strong> partes
                {' '}({Math.round((overlapWarn.overlap_pct || 0) * 100)}%) ya existen en lotes previos.
              </p>
              <p style={{ fontSize: 12, color: '#6b7772', marginTop: 8, marginBottom: 0, lineHeight: 1.5 }}>
                Si continuás, los partes ya existentes se marcarán como Fuera de Alcance y solo se incorporarán los nuevos. ¿Confirmás?
              </p>
            </div>
            <div style={{ padding: '12px 18px', background: '#fafcfb', borderTop: '1px solid #eaeeec', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button style={sS.btnSecondary} onClick={() => setOverlapWarn(null)}>Cancelar</button>
              <button
                style={{ ...sS.btnPrimary, background: '#7a4a00' }}
                onClick={() => { setOverlapWarn(null); handleUploadForce(); }}
              >
                <Icon name="upload" size={13} /> Continuar igual
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
