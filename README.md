# TFG
## 01-03-2026
**Tasques realitzades:**

**DEFINICIÓ DE DADES I ESTRUCTURA INICIAL**

1. <u>Creació base de dades no relacional </u>

    S’ha creat una base de dades en MongoDB (Sense esquema predefinit)

2. <u> Configuració d'un contenidor Docker per a la base de dades + Volum persistent per a l’emmagatzematge de dades. </u>

    Creació docker-compose.yml amb imatge de mongodb


**EXTRACIÓ I INGESTIÓ DE DADES**

Per aquesta tasca s’ha definit un arxiu main.py en el qual es realitzen els següents pasos:

1. <u> Connexió base de dades </u>

    Mitjançant una classe DbClient en el arxiu db_client.py es fa la connexió amb la base de dades tfg_database que tenim a MongoDb creada.

Tot el procés que es menciona a continuació s'ha realitzat en base a un tipus concret d'arxiu: preus extrets d'ENTSO-E desde el 01/01/2025 al 31/12/2025 (període d'un any).

2. <u>  Processament arxius </u>

    Descarrega manual de les dades desde la web ENTSO-E i creació de dues carpetes (ExcelFilesNoProcessed,ExcelFilesProcessed)

    *Actualment aquest procés es realitza de manera manual, es preveu automatitzar-lo mitjançant tècniques com ara l’ús de Selenium (problemes amb el login i doble factor).

3. <u> Extració </u>

    Mitjançant una classe Extractor en el arxiu extractor.py (s’extreuen les dades en funció del format del document)

4. <u> Inserció base de dades </u>

    Mitjançant una classe DbClient en el arxiu db_client.py es fa la connexió amb la base de dades tfg_database que tenim a MongoDb creada.


**ANÀLISIS DE DADES**

**Detecció 1**

En un primer anàlisis per tal de veure si tots els registres s’han guardat correctament s’ha detectat la següent anomalia:

Les dades estan registrades cada 15 minuts durant cada hora i dia de l’any la qual cosa ens genera un total de 35.040 registres (4 * 24 * 365). 

*En anys de 366 dies serien: 35.136

La creació de un petit codi en el arxiu check_db.py ens ha permès detectar una anomalía relacionada amb el nombre de registres guardats.
Aquest ens indica que cada zona conté 35.028 cosa que denota una falta, no molt significativa, de 12 registres per zona.

Després d'un anàlisi dels factors que podrien haver provocat aquest fet s'ha arribat a la següent conclusió:
Els dies on es canvia la hora, en l’any 2025 van estar 30/03 i 26/10.

En aquests les dades tenen un format lleugerament diferent:
1. Cas 30/03
En aquest cas l’hora s'adelante per lo tant tindrem 23 hores en el dia, és a dir, de 02.00 a 03.00 no hi ha dades perquè aquesta hora no existeix.

    ![Descripción de la imagen](images/Cas%201%20(30-03).png)

2. Cas 26/10
En aquest cas l’hora s’atrassa per lo tant tindriem 25 hores en el dia.
    ![Descripción de la imagen](images/Cas%202%20(26-10).png)

Tot i així tindrem 35.028 de 35.040 que sería un 99.96% de dades la qual cosa representa perdre un 0.04% de les dades únicament per utilitzar una plataforma diferent.

Les dues solucions possibles passen per:

1. Adaptar el codi d'extractor.py per aquestes files en concret
2. Utilitzar dades de NordPool (podien contenir anomalíes també)


**Detecció 2**

Amb el mateix codi utilitzat per veure si les insercions son correctes, s'ha detectat un nombre més elevat de registres insertats en un país: França amb 39.631

Això ha provocat la creació d'un segon codi (france_diagnostic.py) per tal de detectar que estava succeïnt i s'ha obtingut que una sèrie de mesos tenien dos registres pel mateix quart horari.

La web ENTSO-E conté dades d'una subasta paral·lela i per això la duplicitat de dades.
Aquest fet també és comú tan a Àustria com a Alemanya (per això encara no estan inserits en base de dades).
![Descripción de la imagen](images/Aus-Ger(DoubleSequence).png)