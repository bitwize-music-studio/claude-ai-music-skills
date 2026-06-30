# Guía Económica para Producción Musical con Suno AI

## Introducción

Esta guía está diseñada para artistas que quieren producir música con Suno AI **sin depender de una cuenta premium de Claude**. El enfoque es educativo y manual, permitiéndote entender cada paso del proceso mientras mantienes el control creativo.

## ¿Por Qué Esta Guía?

El proyecto original `claude-ai-music-skills` está diseñado para automatización completa con Claude Code, lo cual requiere:
- Cuenta de Claude Pro o Max ($20-200/mes)
- Configuración técnica compleja
- Dependencia total de la IA para decisiones creativas

**Esta alternativa te permite:**
- Usar Suno directamente con prompts de calidad profesional
- Aprender el proceso de producción paso a paso
- Mantener control creativo total
- Coste: solo tu suscripción de Suno (gratis o desde $8/mes)

---

## Flujo de Trabajo Simplificado

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   FASE 1:       │────▶│   FASE 2:        │────▶│   FASE 3:       │
│   CONCEPTO      │     │   PROMPTS SUNO   │     │   PRODUCCIÓN    │
│                 │     │                  │     │                 │
│ • Album idea    │     │ • Style Box      │     │ • Generar en    │
│ • Track list    │     │ • Lyrics Box     │     │   Suno          │
│ • Referencias   │     │ • Estructura     │     │ • Iterar        │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                       │                        │
         ▼                       ▼                        ▼
    Documentar              Ordenar                Exportar
    en README               en carpetas            stems finales
```

---

## FASE 1: Concepto del Álbum

### Paso 1.1: Define la Base

Responde estas preguntas en un archivo `README.md`:

```markdown
# [Nombre del Álbum]

## Información Básica

| Campo | Tu Respuesta |
|-------|--------------|
| Artista | |
| Género principal | |
| Subgéneros | |
| Tipo de álbum | (Conceptual / Temático / Colección / Documentary) |
| Número de tracks | |
| Duración target por track | (ej: 3:30-5:00) |

## Concepto Central

¿De qué trata este álbum? (2-3 párrafos)

## Referencias Sonoras

¿Qué artistas/álbumes inspiran este sonido?
- Artista 1: __________ (qué específico te gusta)
- Artista 2: __________ (qué específico te gusta)
- Artista 3: __________ (qué específico te gusta)

## Paleta Emocional

Palabras clave que describen la atmósfera:
- 
- 
- 
```

### Paso 1.2: Estructura del Tracklist

Crea una tabla con el orden tentativo:

```markdown
## Tracklist

| # | Título | Concepto (1 frase) | BPM | Duración | Notas |
|---|--------|-------------------|-----|----------|-------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
```

---

## FASE 2: Creación de Prompts para Suno

### Anatomía de un Prompt Exitoso (Suno V5/V5.5)

#### Style Box (máx 1000 caracteres)

**Fórmula:**
```
[Voz]. [Género + subgénero]. [Instrumentación clave]. [Producción]. [Tempo]
```

**Ejemplo completo:**
```
Male baritone, gritty, emotional delivery. Alternative rock with post-punk influences.
Clean electric guitar with reverb, driving bassline, tight live drums.
Modern production with analog warmth, dynamic range. 120 BPM, A minor.
```

#### Reglas de Oro

1. **Máximo 4-7 descriptores** - Más causa "fatiga del prompt"
2. **Voz PRIMERO** - Suno prioriza lo primero que lee
3. **Sé literal** - V5 entiende instrucciones directas
4. **No uses nombres de artistas** - Suno los bloquea

### Lista de Verificación por Track

Para cada track, crea un archivo `track-01-nombre.md`:

```markdown
# [Nombre del Track]

## Concepto
[2-3 frases sobre qué cuenta esta canción]

## Style Box
```
[Copia aquí tu style prompt completo]
```

## Exclude Styles (opcional, máx 2-4 items)
```
no drums
no electric guitar
```

## Lyrics Box
```
[Intro]

[Verse 1]
[Línea 1]
[Línea 2]
[Línea 3]
[Línea 4]

[Chorus]
[Línea 1]
[Línea 2]
[Línea 3]
[Línea 4]

[Verse 2]
...

[Bridge]
...

[Chorus]
...

[Outro]
[End]
```

## Configuración Suno

| Campo | Valor |
|-------|-------|
| Model | V5 o V5.5 |
| Instrumental | Sí / No |
| Duration | Target (ej: 4:00) |
| Weirdness | 0-100 (default 50) |
| Style Influence | 0-100 (default 50) |

## Log de Generaciones

| # | Fecha | Resultado | Rating (1-5) | Notas |
|---|-------|-----------|--------------|-------|
| 1 | | ✅/❌ | | |
| 2 | | ✅/❌ | | |
```

### Guía de Géneros Comunes

#### Hip-Hop / Rap
```
[Subgénero: boom bap / trap / lo-fi / nerdcore], [beat style: 808s / sampled drums],
[vocal flow description], [tempo BPM]
```

#### Rock Alternativo
```
Alternative rock with [influencia: britpop / grunge / post-punk],
[instrumentación: distorted guitars / driving bass], [vocal: gritty / melodic]
```

#### Electrónica
```
[Subgénero: house / techno / IDM / synthwave], [synth type: analog / digital],
[BPM crítico para dance], [atmósfera]
```

#### Folk/Acústico
```
Acoustic folk, [instrumentos: fingerpicking / banjo / mandolin],
[vocal: intimate / breathy], [tempo], [mood]
```

### Problemas Comunes y Soluciones

| Problema | Solución |
|----------|----------|
| Voces enterradas en la mezcla | Pon descripción vocal PRIMERO en Style Box |
| Género incorrecto | Sé más específico con subgénero |
| La canción se corta temprano | Añade `[Outro]` y `[End]` al final |
| Secciones repetitivas | Usa tags de sección claramente, varía letras |
| Pronunciación mala | Usa spelling fonético (ej: "Lin-ucks" para Linux) |
| Elementos no deseados | Usa Exclude Styles (máx 2-4 items) |

---

## FASE 3: Producción en Suno

### Paso 3.1: Preparación

1. **Organiza tus archivos**
   ```
   album-name/
   ├── README.md (concepto general)
   ├── tracks/
   │   ├── track-01-apertura.md
   │   ├── track-02-nombre.md
   │   └── ...
   └── exports/
       └── (stems descargados de Suno)
   ```

2. **Prepara una lista de verificación maestra**
   ```markdown
   ## Estado de Producción
   
   | Track | Prompt Listo | Generado | Stems Descargados | Masterizado |
   |-------|-------------|----------|-------------------|-------------|
   | 01 | ✅ | ❌ | ❌ | ❌ |
   | 02 | ✅ | ✅ | ❌ | ❌ |
   ```

### Paso 3.2: Generación Iterativa

**Proceso recomendado:**

1. **Primera generación** - Prueba el prompt tal cual
2. **Evalúa** (usa checklist de calidad abajo)
3. **Ajusta** - Modifica 1-2 elementos del prompt
4. **Regenera** - Máximo 3-5 iteraciones por track
5. **Selecciona** - Marca la mejor versión con ✓

### Checklist de Calidad

Antes de marcar un track como "completado":

- [ ] Claridad vocal y pronunciación
- [ ] Género/estilo coincide con intención
- [ ] Tono emocional apropiado
- [ ] Balance de mezcla (voces no enterradas)
- [ ] Estructura sigue los tags de sección
- [ ] No hay cortes raros o loops
- [ ] No hay instrumentos no deseados

### Paso 3.3: Exportación y Organización

1. **Descarga stems** desde Suno (disponible en planes Pro+)
2. **Nombra consistentemente**:
   ```
   album-track01-vocals.wav
   album-track01-drums.wav
   album-track01-bass.wav
   album-track01-mixed.wav
   ```

3. **Documenta URLs** de Suno en tu track file:
   ```markdown
   ## URLs de Suno
   - Versión final: https://suno.com/song/xxxxx
   - Alternativas: https://suno.com/song/yyyyy
   ```

---

## Apéndices

### A: Homófonos Comunes (Pronunciación)

Suno puede malinterpretar estas palabras:

| Palabra | Pronunciación Correcta | Fonético para Suno |
|---------|----------------------|-------------------|
| lead (verbo) | /liːd/ | leed |
| lead (metal) | /lɛd/ | led |
| read (presente) | /riːd/ | reed |
| read (pasado) | /rɛd/ | red |
| live (vivir) | /lɪv/ | liv |
| live (en vivo) | /laɪv/ | lyve |
| tear (lágrima) | /tɪər/ | teer |
| tear (romper) | /tɛər/ | tair |

### B: Tags de Estructura Reconocidos

```
[Intro] - Introducción instrumental o vocal
[Verse] - Verso narrativo
[Pre-Chorus] - Pre-coro, construye tensión
[Chorus] - Coro, hook principal
[Post-Chorus] - Post-coro, extensión del hook
[Bridge] - Puente, cambio de dinámica
[Rap Verse] - Verso rapeado (diferencia de canto)
[Guitar Solo] - Solo instrumental
[Instrumental] - Sección sin voz
[Dance Break] - Break bailable (electrónica)
[Outro] - Salida, fade out
[End] - Señal de fin definitivo
```

### C: Duración y Estructura

| Duración Target | Estructura Recomendada |
|----------------|------------------------|
| < 2:00 | [Intro] → [Main Theme] → [End] |
| 2:00-3:00 | [Intro] → [V1] → [Chorus] → [V2] → [Chorus] → [Outro] → [End] |
| 3:00-5:00 | Estándar: V1, Pre, Chorus, V2, Pre, Chorus, Bridge, Chorus, Outro |
| > 5:00 | Extendida: añade V3, solos instrumentales, puentes adicionales |

### D: Recursos Adicionales

- **Documentación oficial Suno**: https://suno.com/wiki
- **Guía V5 Best Practices**: `/workspace/reference/suno/v5-best-practices.md`
- **Lista de géneros**: `/workspace/reference/suno/genre-list.md`
- **Guía de pronunciación**: `/workspace/reference/suno/pronunciation-guide.md`

---

## Conclusión

Esta guía te permite producir música de calidad profesional con Suno AI **sin automatización costosa**. El proceso manual tiene ventajas:

✅ **Control creativo total** - Tú decides cada detalle
✅ **Aprendizaje profundo** - Entiendes por qué funciona cada prompt
✅ **Coste mínimo** - Solo Suno, sin Claude premium
✅ **Portabilidad** - Las plantillas funcionan en cualquier editor de texto

**Próximos pasos:**
1. Copia esta guía a tu carpeta de proyecto
2. Completa la Fase 1 con tu concepto de álbum
3. Usa las plantillas de la Fase 2 para cada track
4. Sigue el proceso iterativo de la Fase 3

¡Buena creación! 🎵
