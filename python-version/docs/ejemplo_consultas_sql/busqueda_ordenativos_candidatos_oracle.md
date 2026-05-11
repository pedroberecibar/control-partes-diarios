Caso A:
	suministro -> ordenativo CE
Caso B: 
	medidor colocado -> suministro -> ordenativo CE
	+
	medidor retirado -> suministro -> ordenativo CE


Consulta para obtener ordenativos CE en el caso B:

SELECT * 
FROM xxsigec.ordenativos 
WHERE TOR_CODIGO = 'CE'
  AND SRV_CODIGO = (
      SELECT SRV_CODIGO
      FROM XXSIGEC.EQUIPOS
      WHERE STE_NUMERO = '7180777'  --> Este seria el numero de medidor colocado 
      ORDER BY EQP_FECHA_INSTAL DESC
      FETCH FIRST 1 ROWS ONLY  --> Para obtener el ultimo suministro (fecha de instalacion mas reciente)
  );
