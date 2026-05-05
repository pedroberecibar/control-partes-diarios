SELECT 
    ORD_NUMERO,
    "GABINETE",
    "SUBTERRANEO",
    "ALTURA",
    "AEREO",
    "EQUIPO_MEDICION_REEMPLAZADO",
    "ACOMETIDA_REALIZADA",
    "TAPA_REEMPLAZADA",
    "EQUIPO_DE_MEDICION_INSTALADO"
FROM (
    -- 1. Primero filtramos y traemos solo los datos crudos que necesitamos
    SELECT 
        obs_ord.ORD_NUMERO, 
        obs_ord.TOB_CODIGO, 
        obs_ord.TOB_DESCRIPCION
    FROM xxsigec.xxco_observaciones_ordenativ_v obs_ord
    INNER JOIN xxsigec.ordenativos ord 
        ON ord.ord_numero = obs_ord.ord_numero
    WHERE ord.tor_codigo = 'CE'
      AND ord.sec_codigo_origen = 'PROTELEM'
      AND obs_ord.ORD_NUMERO = '79046730'
)
-- 2. Oracle hace la magia de pivotar automáticamente sin GROUP BY
PIVOT (
    MAX(TOB_DESCRIPCION)
    FOR TOB_CODIGO IN (
        'APP4SITIO_3' AS "GABINETE",
        'APP4SITIO_4' AS "SUBTERRANEO",
        'APP4SITIO_2' AS "ALTURA",
        'APP4SITIO_1' AS "AEREO",
        'APP4TRAB_1'  AS "EQUIPO_MEDICION_REEMPLAZADO",
        'APP4TRAB_2'  AS "ACOMETIDA_REALIZADA",
        'APP4TRAB_3'  AS "TAPA_REEMPLAZADA",
        'APP4TRAB_4'  AS "EQUIPO_DE_MEDICION_INSTALADO"
    )
);

