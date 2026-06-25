# Tradutor Libras

Aplicação desktop que converte fala em português para **Língua Brasileira de Sinais (Libras)** em tempo real, exibindo um avatar 3D animado que realiza os sinais correspondentes.

---

## Como funciona

```
Microfone → Transcrição (Google Speech) → VLibras (avatar 3D) → Sinais em Libras
```

1. O usuário fala (modo manual ou ao vivo)
2. O áudio é transcrito pela API do Google Speech Recognition
3. O texto é enviado ao player **VLibras** (ferramenta oficial do Governo Federal)
4. O avatar 3D executa os sinais em Libras automaticamente

---

## Requisitos

- Python 3.10+
- Conexão com a internet (Google Speech API + VLibras)
- Microfone

### Instalar dependências

```bash
pip install -r requirements.txt
```

> **Windows**: pode ser necessário instalar drivers de áudio PortAudio para o `sounddevice`:
> ```bash
> pip install sounddevice
> ```
> Se houver erro de DLL, baixe o PortAudio em https://www.portaudio.com

---

## Executar

```bash
python main.py
```

---

## Modos de uso

### Modo Manual (padrão)
- **Segure ESPAÇO** enquanto fala
- **Solte ESPAÇO** para transcrever e traduzir
- O avatar executa os sinais automaticamente

### Modo Ao Vivo
- Clique no botão **"Ao vivo"** na barra superior
- O sistema detecta automaticamente quando você começa e para de falar
- Cada frase é enviada ao VLibras assim que um silêncio é detectado (~1,5s)
- O texto acumula no painel esquerdo
- Clique **"Parar ao vivo"** para encerrar

---

## Interface

| Painel | Conteúdo |
|---|---|
| Esquerda | Texto transcrito |
| Direita | Avatar VLibras em Libras |

---

## Tecnologias

| Componente | Tecnologia |
|---|---|
| Interface gráfica | PyQt5 |
| Captura de áudio | sounddevice + NumPy |
| Reconhecimento de voz | Google Speech Recognition API |
| Tradução para Libras | VLibras (RNDS / Governo Federal) |
| Renderização do avatar | Unity WebGL via QWebEngineView |

---

## Estrutura do projeto

```
Tradutor Libras/
├── main.py          # Aplicação principal (PyQt5)
├── vlibras.html     # Página web com o widget VLibras embutido
├── requirements.txt # Dependências Python
└── README.md
```

---

## Sobre o VLibras

O [VLibras](https://www.vlibras.gov.br) é uma suíte de ferramentas do Governo Federal Brasileiro desenvolvida pela RNDS/SEAD em parceria com o LAVID/UFPB, com o objetivo de tornar conteúdo digital acessível para pessoas surdas por meio da tradução automática para Libras.
