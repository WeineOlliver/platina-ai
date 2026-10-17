# Roteiro de Vídeo para o Canal YouTube (OlliverW9 / Tech)

**Título Sugerido:**  
*Como criei um Assistente de IA que impede você de PERDER troféus no PlayStation (com Node.js, Python e AWS)*

**Duração estimada:** 10 a 14 minutos  
**Público-alvo:** Desenvolvedores, caçadores de platina e recrutadores de tecnologia.

---

### [00:00 - 01:30] Hook & O Problema Real
- **Visual:** Gravação de tela de *Bloodborne* ou *Elden Ring* morrendo ou mostrando um troféu bloqueado. Câmera no rosto.
- **Fala:** 
  > *"Você já perdeu 40 ou 50 horas da sua vida em um jogo porque esqueceu de falar com um NPC antes de passar a névoa de um chefe? Se você caça platinas no PlayStation como eu, você sabe o ódio que dá o famoso troféu missable (perdível).*
  > *Pra resolver isso de uma vez por todas, eu decidi construir o **Platina AI**: um assistente inteligente que lê o meu save em tempo real, monitora os guias da PowerPyx usando inteligência artificial e me avisa antes que eu faça besteira. Hoje eu vou te mostrar como construí toda a arquitetura dele do zero!"*

---

### [01:30 - 04:00] Por que o ChatGPT falha aqui? (RAG & pgvector)
- **Visual:** Comparação lado a lado: pergunta no ChatGPT genérico alucinando informações vs Platina AI citando o guia oficial.
- **Fala:**
  > *"Se você perguntar pro ChatGPT como pegar o troféu da Eileen the Crow, ele inventa passos que não existem. Por isso usei a arquitetura RAG (Retrieval-Augmented Generation).*
  > *Eu criei um microserviço em Python com FastAPI que divide os guias em parágrafos semânticos, gera vetores de 1536 dimensões e armazena tudo no PostgreSQL com a extensão pgvector. Quando o robô pesquisa, ele faz uma busca por similaridade de cosseno em milissegundos."*

---

### [04:00 - 07:00] O Agente Autônomo com Tool Use (ReAct)
- **Visual:** Demonstração no terminal rodando `POST /api/v1/agent/run` e a resposta em streaming aparecendo no terminal ou na UI local.
- **Fala:**
  > *"O diferencial do Platina AI é que ele é um Agente Autônomo. Ele não só responde perguntas, ele toma decisões.*
  > *No backend em Node.js com Fastify e TypeScript, implementei o padrão ReAct. Quando eu pergunto 'O que devo jogar hoje em Bloodborne?', ele primeiro usa uma ferramenta pra consultar a minha conta na PSN. Ele vê que matei o Padre Gascoigne, mas a Eileen tá pendente. Ele mesmo decide chamar a segunda ferramenta pra pesquisar no banco de dados e me manda um briefing com um checklist antes de eu tocar no controle."*

---

### [07:00 - 09:30] Conectando no Claude Desktop via MCP (Model Context Protocol)
- **Visual:** Abrindo o aplicativo do Claude Desktop no Mac e mostrando a ferramenta do Platina AI integrada nativamente.
- **Fala:**
  > *"E se eu não quiser abrir um site? Eu implementei um servidor do Model Context Protocol (o protocolo aberto MCP lançado pela Anthropic). Isso significa que eu posso abrir o Claude Desktop no meu computador e conversar com meus troféus diretamente pelo aplicativo oficial do Claude!"*

---

### [09:30 - 12:00] Infraestrutura na Nuvem & FinOps (Gastando apenas $1.00 na AWS)
- **Visual:** Mostrando os arquivos Terraform e o dashboard da AWS.
- **Fala:**
  > *"Pra colocar isso em produção, eu criei toda a infraestrutura com Terraform e Kubernetes via Helm. A gente tem VPC com 3 camadas, banco de dados gerenciado no RDS e contêineres Docker.*
  > *Mas como é um projeto de portfólio, eu não queria uma conta gigante da AWS. Então eu configurei o k3s rodando num processador ARM Graviton da Amazon e coloquei um alarme de orçamento que me avisa se a fatura passar de 1 dólar! E no final, tenho um script que destrói tudo com um único comando."*

---

### [12:00 - 13:30] Conclusão & Código Aberto
- **Visual:** Mostrando o repositório aberto no GitHub com 52 perguntas de entrevista técnica.
- **Fala:**
  > *"O projeto é 100% código aberto, tem testes automatizados no GitHub Actions e documentei mais de 50 perguntas técnicas de entrevista pra quem quer se preparar pra vagas remotas internacionais.*
  > *O link do repositório tá na descrição. Se você curtiu, deixa o like e se inscreve no canal!"*
