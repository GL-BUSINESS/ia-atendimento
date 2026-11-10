# Manifesto da revisão 0911 (2026-11-10T09:00:20-03:00)
## Pontas remotas (git ls-remote) × origin/main local
- ia-atendimento: remoto 9a4bacabf247bf3ad0204d5b3e08c9a263a65855 local 9a4bacabf247bf3ad0204d5b3e08c9a263a65855 IGUAL
- bancos-duble: remoto ca3ed2cf5ee6a5e8a03739946bae9698bbb5d438 local ca3ed2cf5ee6a5e8a03739946bae9698bbb5d438 IGUAL
- gl-gateway: remoto 92e97548eb38c80a5f2808bb88a82d09693c99e9 local 92e97548eb38c80a5f2808bb88a82d09693c99e9 IGUAL
- facta-on: remoto 8c3e5abc7cd615d2fda350ee0b203f8170bf8e95 local 8c3e5abc7cd615d2fda350ee0b203f8170bf8e95 IGUAL
- cliente360-api: remoto 6e9c62dea06fb72e5180bfe9be738e7568f7db2f local 6e9c62dea06fb72e5180bfe9be738e7568f7db2f IGUAL
- cliente360-web: remoto 9f0fc5f584b01882696441fe7ece622a8b865a14 local cd4d9fc36a4a4cd577fb6cc3b1477bec61ff8044 DIFERENTE
## Exportações (repo | ref | sha | arquivos | KB)
| ia-atendimento | origin/main | 9a4bacabf247bf3ad0204d5b3e08c9a263a65855 | 257 | 3832 |
| ia-atendimento | origin/feat/b1-6a | 9a714e39fa9520c0188fb32512aec9463ff53ae1 | 243 | 3704 |
| ia-atendimento | feat/esteira | 9e1afe39fde0a9d2d24d8e5fc1f3bad88292295b | 49 | 696 |
| ia-atendimento | kits/s4 | 148cc72db406310831684d89d9349fe1d27a4dd7 | 48 | 708 |
| bancos-duble | origin/main | ca3ed2cf5ee6a5e8a03739946bae9698bbb5d438 | 101 | 1136 |
| gl-gateway | origin/main | 92e97548eb38c80a5f2808bb88a82d09693c99e9 | 38 | 440 |
| facta-on | origin/main | 8c3e5abc7cd615d2fda350ee0b203f8170bf8e95 | 209 | 4056 |
| cliente360-api | origin/main | 6e9c62dea06fb72e5180bfe9be738e7568f7db2f | 811 | 11032 |
## Ramos locais ia-atendimento
  ci/sha256-gitleaks         30bb717 [origin/ci/sha256-gitleaks] fix: sha256 do CI sem o caminho dobrado e gitleaks estrito no portão local
+ feat/b1-1-estado           edc4dc8 (/home/danilo/wt-ia/ia-atendimento-b11) [origin/feat/b1-1-estado] fix: tipos — documento por normalizaç
+ feat/b1-2-linha-tempo      5b29b47 (/home/danilo/wt-ia/ia-atendimento-b12) [origin/feat/b1-2-linha-tempo] Merge remote-tracking branch 'or
+ feat/b1-3-fila             a1c6494 (/home/danilo/wt-ia/ia-atendimento-b13) [origin/feat/b1-3-fila] test: prontidão usa a próxima migração 
+ feat/b1-4-agente-turno     c4d70d3 (/home/danilo/wt-ia/ia-atendimento-b14) [origin/feat/b1-4-agente-turno: behind 71] docs: revisões 1 e 2
+ feat/b1-5-api-entrada      51da2fa (/home/danilo/wt-ia/ia-atendimento-b15) [origin/feat/b1-5-api-entrada] docs: contagem final de testes (
+ feat/b1-6a                 9a714e3 (/home/danilo/wt-ia/ia-atendimento-b1-6a) [origin/feat/b1-6a] docs: bloco de código da revisão no forma
+ feat/b1-8                  def8615 (/home/danilo/wt-ia/ia-atendimento-b1-8) [origin/feat/b1-8: behind 1] docs: revisão da B1.8 e o destino
+ feat/b2-4-pessoas-teste    fdc1b1b (/home/danilo/wt-ia/ia-atendimento-b24) [origin/feat/b2-4-pessoas-teste: behind 27] docs: revisões 1 e 
+ feat/b5-1                  0c072bc (/home/danilo/wt-ia/ia-atendimento-b5-1) [origin/feat/b5-1: behind 10] docs: revisão independente da B5
+ feat/b5-7a-agenda-extrator 5e5cc59 (/home/danilo/wt-ia/ia-atendimento-b57a) [origin/feat/b5-7a-agenda-extrator] Merge remote-tracking bran
+ feat/b5-7b-pausado         48ae1e9 (/home/danilo/wt-ia/ia-atendimento-b57b) [origin/feat/b5-7b-pausado] docs: revisões 1 e 2 da B5.7b
+ feat/b8-1a-corpus          e2abb0d (/home/danilo/wt-ia/ia-atendimento-b81a) [origin/feat/b8-1a-corpus] merge: origin/main (v0.2.0) em feat
+ feat/esteira               9e1afe3 (/home/danilo/wt-ia/ia-atendimento-esteira) [origin/main: ahead 2, behind 178] fix: credencial do regis
+ fix/achados-integracao-d06 db532c5 (/home/danilo/wt-ia/ia-atendimento-integra) [origin/fix/achados-integracao-d06] fix: achados R-02 a R-0
  integra/b1-8               74bc6ae [origin/feat/b1-8] test: aplicadores concorrentes afirmam cada migração uma vez, não um só aplicador
  integra/b5-1               0ff6aa9 [origin/feat/b5-1] chore: traz a correção do teste de aplicadores concorrentes da feat/b1-8
+ kits/s4                    148cc72 (/home/danilo/wt-ia/ia-atendimento-kits-s4) [origin/main: ahead 1, behind 178] feat: kit s4 (papéis, pg
* main                       24bc524 [origin/main: behind 134] Merge pull request #5 from GL-BUSINESS/feat/b8-1a-corpus
+ sim/integra-0411           84c1f8a (/home/danilo/wt-ia/integra-0411-ia) Merge branch 'integra/b5-1' into sim/integra-0411
## Worktrees
/home/danilo/repos/ia-atendimento           24bc524 [main]
/home/danilo/wt-ia/ia-atendimento-b1-6a     9a714e3 [feat/b1-6a]
/home/danilo/wt-ia/ia-atendimento-b1-8      def8615 [feat/b1-8]
/home/danilo/wt-ia/ia-atendimento-b11       edc4dc8 [feat/b1-1-estado]
/home/danilo/wt-ia/ia-atendimento-b12       5b29b47 [feat/b1-2-linha-tempo]
/home/danilo/wt-ia/ia-atendimento-b13       a1c6494 [feat/b1-3-fila]
/home/danilo/wt-ia/ia-atendimento-b14       c4d70d3 [feat/b1-4-agente-turno]
/home/danilo/wt-ia/ia-atendimento-b15       51da2fa [feat/b1-5-api-entrada]
/home/danilo/wt-ia/ia-atendimento-b24       fdc1b1b [feat/b2-4-pessoas-teste]
/home/danilo/wt-ia/ia-atendimento-b5-1      0c072bc [feat/b5-1]
/home/danilo/wt-ia/ia-atendimento-b57a      5e5cc59 [feat/b5-7a-agenda-extrator]
/home/danilo/wt-ia/ia-atendimento-b57b      48ae1e9 [feat/b5-7b-pausado]
/home/danilo/wt-ia/ia-atendimento-b81a      e2abb0d [feat/b8-1a-corpus]
/home/danilo/wt-ia/ia-atendimento-esteira   9e1afe3 [feat/esteira]
/home/danilo/wt-ia/ia-atendimento-integra   db532c5 [fix/achados-integracao-d06]
/home/danilo/wt-ia/ia-atendimento-kits-s4   148cc72 [kits/s4]
/home/danilo/wt-ia/ia-atendimento-main-b2-1 9bee6a4 (detached HEAD)
/home/danilo/wt-ia/integra-0411-ia          84c1f8a [sim/integra-0411]
/home/danilo/repos/bancos-duble           1305152 [main]
/home/danilo/wt-ia/bancos-duble-a63       fac8ec3 [feat/b2-4-pessoas-teste]
/home/danilo/wt-ia/bancos-duble-b2-1      f753493 [feat/b2-1]
/home/danilo/wt-ia/bancos-duble-integra   add1614 [fix/achados-integracao-d06]
/home/danilo/wt-ia/bancos-duble-main-b16a f6ec889 (detached HEAD)
/home/danilo/wt-ia/integra-0411-duble     1a32017 [sim/integra-0411]
/home/danilo/repos/gl-gateway                                                              560c45d (detached HEAD)
/home/danilo/wt-ia/gl-gateway-b60                                                          faacd93 [feat/ia-projecao-hmac]
/home/danilo/wt-ia/gl-gateway-fix-rotas                                                    5b191b1 [fix/rotas-sem-colunas]
/tmp/claude-1001/-opt-claude/c3edfc59-52d9-4e44-8d0b-adab74392dfc/scratchpad/wt/gl-gateway 80aceaf (detached HEAD)
/home/danilo/repos/facta-on                                                              2a0b6f1 (detached HEAD)
/home/danilo/credit-intel-discovery/src/facta-on                                         dac74ce (detached HEAD)
/home/danilo/repos/facta-on/.worktrees/c360-caminhos                                     856655d [feat/c360-caminhos]
/home/danilo/wt-facta-bairro-bytes                                                       151b84f [fix/bairro-limite-bytes]
/home/danilo/wt-facta-datas-valor-af                                                     28f14a2 [test/datas-relativas-valor-af] prunable
/home/danilo/wt-facta-on-extra                                                           e463e83 [feat/c360-extra] prunable
/home/danilo/wt-facta-recusa-sem-teto                                                    125ee59 [fix/politica-recusa-sem-teto]
/home/danilo/wt-facta-reprovados                                                         741b603 [feat/c360-recusas-fato]
/home/danilo/wt-ia/facta-on-tap                                                          1d51684 [feat/tap-retornos]
/home/danilo/wt-motivo/facta-on                                                          2929d0a [feat/c360-motivo-cancelamento] prunable
/home/danilo/wt-pa-s4/P-FA-9-view                                                        438a407 [feat/c360-base-offline-view]
/home/danilo/wt-pa-s4/T2.2-facta                                                         7c1822f [feat/dados-fonte]
/home/danilo/wt-pa-s4/T2.3-facta                                                         3145d70 [feat/c360-diario]
/home/danilo/wt-pa-s4/T2.5-facta                                                         5833ca9 [feat/c360-contexto]
/home/danilo/wt-pa-s4/T5.2-facta                                                         f4e6a9e [feat/consulta-fato-lote]
/home/danilo/wt-pa-s4/T5.2-facta-f6e6cac                                                 f6e6cac (detached HEAD)
/home/danilo/wt-pa-s4/T5.6-facta                                                         f4f2e2f [feat/consulta-fato-lote-limpo]
/home/danilo/wt-pa-s4/T6-facta-limite                                                    773b7a1 [fix/c360-pos-limite-diario]
/home/danilo/wt-rev-facta29                                                              d911288 (detached HEAD) prunable
/home/danilo/wt-rev-facta30                                                              42c77c2 (detached HEAD) prunable
/home/danilo/wt-rev-facta30-main                                                         28e141c (detached HEAD) prunable
/tmp/claude-1001/-opt-claude/c3edfc59-52d9-4e44-8d0b-adab74392dfc/scratchpad/wt/facta-on e9ba005 (detached HEAD)
## PRs abertos
### ia-atendimento
#13 feat/b1-6a draft=false mergeable=CONFLICTING 2026-11-04T19:08:16Z feat: B1.6a — ledger t11 com cerca, executar_efeito, gasto Σ, ia_ativa relida, lease de espera e expirar_parados (+ correção da revisão)
### bancos-duble
### gl-gateway
### facta-on
#49 feat/tap-retornos draft=true mergeable=CONFLICTING 2026-11-03T13:12:00Z feat: tap de retornos da FACTA sem PII (flag off) + filtro de CPF no log de acesso
#16 feat/vendedor-por-intencao draft=false mergeable=UNKNOWN 2026-09-30T03:25:41Z feat(vendedor): intenção de digitação durável — robô 85 só com prova de origem robô
#15 fix/facta-retrato-precedencia draft=false mergeable=UNKNOWN 2026-09-30T01:59:25Z fix(esteira): precedência do retrato FACTA no mesmo minuto (flag off, 0.10.0)
## Kits (sha256)
4909ab862224b802cc195f34f38026b72333ad2f51151c727dad7466ff06444c  ./config/chats-teste.sh
1be63297893fcd7880fdcd7fa8963d67c80d822f93055c98f7be90b0742638c5  ./gateway/aguardar-reinicio.sh
6c86b1d374bbb47e026e3daea66f718d1da14f2fef57b2299231faf9b9dde868  ./gateway/ativar-sumidouro.sh
26a1062aafb2c480c9e261d60ab5af48fef803e24f956fe046b14f03ccbe2225  ./gateway/desfazer.sh
9dfa38bcb2170df13c17f4c28a8582cb3e57fab9395b04a7e73ee7e5d109a6ce  ./gateway/e12-sumidouro.sh
f7905c8eb56dad13b7d5ffca244ac8b66c788738b4f6bd45bbbab1285c61b383  ./gateway/ensaio-local.sh
b49ac7aec8bb92068c00170be0f260904282af8818a1e9c81cfae95cd6f14f9b  ./gateway/ensaio_stub.py
206205cc3310ff7f56a7e590d17cfe8a5a95146e4c00bad47332ecd553a1796c  ./gateway/entregar-hmac-vps.sh
2f353a879b385650269f120b51c8dc85a691083b8e551f448e3458f94008eff3  ./gateway/env-gateway.sh
3b0737deda6a7af898ddd82238b1d8cfcd439797b0818f395d92d6b616161b7e  ./gateway/ia-sumidouro.workflow.json
4b55c2f0905ea68698089862b43d8357dfc1c30894a59dc575268ec7a1dcb52a  ./gateway/lib.sh
671d592074089b57460bdb8718ed60b9e9b166e8245e79e7da0f3155603d8739  ./gateway/migrar.sh
12e7804b036e21027af7e1ab6ab8591bb4210e7172f2fc6503a599d55f3ef8f6  ./gateway/montar_env.py
8669b84cb996cf7bfa4a88b320780ce022ee8bfdf3d062810f2f6b9eaee1afb2  ./gateway/portao.sh
2889705ede06b2e1cd285e61157f555cc2a36ca81e581970c1a0ad6db27ba1ee  ./gateway/README.md
25321b28464524865316e529a48a4dcf3558f7967335ce84a46e0889047438f4  ./gateway/rotas-ia.sh
da1129393d11082efb42cd45542af6ff439a28dbd1cf4097c10b38095e7c5f77  ./gateway/sql/migra_rotas_ia.sql
00b077b2544c249c39f833545c05bbafc1e0db44655d82aae0c745b5d6e50418  ./gateway/vigia.sh
aff9654bfc08541f86583c34f62e3379a071ea075928d2023f6a2122c1263363  ./merge-0411/merge-0411.sh
7854d9d271081ca23f259e9236835a28b6ebc586e2066803dcc7a51b936f0a35  ./merge-d06/merge-d06.sh
13e478106894375a11483e90609db965f56f04cdd5de910615dbc5801ac80e6b  ./s4/desfazer.sh
b70ffdb6321674701bb7d58c80ec4348121dc75fb9e555298c6781247c356b82  ./s4/distribuir-certs.sh
dd383c979d1eb62d8fcabc96d3181b97b52fb76211bb55217b379461d31f7421  ./s4/ensaio-local.sh
7719d5ce287f734e83b88735639ad7ab35daa9de3b2ec3f4f289ec83a8638df6  ./s4/lib.sh
93280d393f9b42203bfc6f391550e58de820929b76bcecca9cbcf0d1dd30fda5  ./s4/provar.sh
a2e50bd3d3f54876ec3773ff5e8a5e00e871f12de1ac76dbb7f9f2099aabf22f  ./s4/README.md
f6458b2e34c6d0c8bf66ab2de65c8e5ee8430022c4769676a23cc9356a446264  ./s4/s4-hba.sh
622ff46f46afe5d4cbabea550064fb29a3da66c14fff692a4166303273b9710c  ./s4/s4-papeis.sh
## Kits omitidos (0600/segredo/binário): só nome
## Papel vigente (sha256)
508cab01f033a1612c499c5026c5d6a7ba122ba6e53ca32e99808e0b8a32f95b  ROTEIRO-DE-ACAO.md
1cfa9f7be4bd0dc92de27b326863c0ffea896f8be27bb92a1e2c7b01327c0fe5  RETOMAR-0911.md
7d5c74c40bf1e2232dbceda165cdb5db699243b3264a57dfead5a9712ce18e6a  contratos/01-gl-gateway.md
d8812a9b66c04ff27ca19d3a3b8979d27f2cc79518970ec5b45ff53f867cf3d3  contratos/01-gl-gateway.v1.md
355a9946f11e40069389c1971217775e82ccd5e4c811da7678bec14663f76011  contratos/01-gl-gateway.v2.1.md
5e96d43199ca8993c42751607a4d1264d34bc51eb91735640b5fa9e0a41c090f  contratos/01-gl-gateway.v2.2.md
76721c5be285fd55602177c02124a35d83bdacf7704b47566a983997c3b2b264  contratos/01-gl-gateway.v2.3.md
22ddbcce57c20b137507707b8998a7e54e8e06d9f80e33c233263bde0c02f99b  contratos/01-gl-gateway.v2.4.md
99fddab4fa57d41fed5725be92dc60709caa91c1f50c3f29f6b76f3f0b287f2e  contratos/01-gl-gateway.v2.md
a2c98604d2c245a7025ed213890f7f32ed54e11ba9f1741f750a29330beca6c5  contratos/02-chatguru-api.md
8c0bc72491797a7e48ae2da9f1a3f8107ba500497c38b29e84a3cadf559cf932  contratos/02-chatguru-api.v1.md
35c0d59953abe618908ce8b08d36c516abff8a64580c5afffb7da2aaffb1c85d  contratos/03-cliente360-api.md
e2600da7f422d9c07f9e8b172693f7846b703338ab59969eb6be922fa7b44322  contratos/03-cliente360-api.v1.md
89199c1047bedaa61f038a14d9f4f896267068ab2a9a2c7f00041e97def7e042  contratos/03-cliente360-api.v2.1.md
c16df6ba5d25eae6fc6d8d2e1e1833c1315156baa740f4d7fe089e5194a94ffc  contratos/03-cliente360-api.v2.md
dfda5d5c87c8ff73cd4549ae8e8ab09316f70ad11ea22378aa7021e7397a1b0a  contratos/04-n8n-braco-espelho.md
ec34a2d2417e9faca85f1ab0a9c472ac140604cd0605b3f6357be52a0dafb2eb  contratos/04-n8n-braco-espelho.v1.md
54d2ec55204466845b7952be0cc7180281c4bbfa952c80dbd591d86572089a86  contratos/04-n8n-braco-espelho.v2.1.md
0caa2b8f09d50c7fc13e8d5f1907e87ae4329906677a0ac2360aefe7a5fcf916  contratos/04-n8n-braco-espelho.v2.md
b8694ee37763e4a40b840501825aa9fed96af94609513d084b68ff6903e1447a  contratos/05-facta-on.md
7f758e17c61568c3d528f2c0baae75e5a8c0bc47a174ec2c60bff55f4f0d985a  contratos/05-facta-on.v1.md
2dc6fb374fc0286b17331af0e0b988b80793a78c0eb15c3e5b27ec8c12aa79ac  contratos/05-facta-on.v2.md
eea2cd47be83cad2efc75409765b4961e6128fa126b964eac53a11af4b3be0b0  contratos/06-iskra.md
cc1f7dfc905de56048476fb7544e08eb24ef074a2a54a49a809ecd754f66db87  contratos/06-iskra.v1.md
2c6519f54e65c1d945e1f49ada018f9bd37e14a3ac47e77a526d0af0531d06cd  contratos/07-cliente360-web.md
6fad94c3fe500137b561adf692ee1d655ee26c3cb719d1bfb5a6dc49aca1fd20  contratos/07-cliente360-web.v1.md
be3a33016a504d2bcb8b09eefae9be18e996c8533ac2ca4633c6f1ccc467e3b5  contratos/07-cliente360-web.v2.1.md
f201958e3a921a6f34a5c45c6b0cd4ee9e4cdf714e35315f25ab74185f63b326  contratos/07-cliente360-web.v2.md
16802059764f7940147d95e1f1a4ec59217d8e744ae3be5c032ee180d73df17d  contratos/08-orquestrador.md
c2c714ee68a67d854210f067d5f5fa603641fe8275b529a1e9f6d8eab56b4ac9  contratos/08-orquestrador.v1.md
2b88ff003078e82eeac3d02ebc068e675f14938ccb08d5203bc3db9552e3c015  contratos/08-orquestrador.v2.1.md
a9001d9614873a5eb56fe3839e12149bdb60b8b04f2418aaeff2916790246313  contratos/08-orquestrador.v2.2.md
c3c5f47abf95215537b96f8900e09713c1dfdc7ad7789d7c4034e9a0d68dea24  contratos/08-orquestrador.v2.3.md
9c152c49a6213fb93179f69bc148a5e2cda5680390ae43b5d85f84de92542c22  contratos/08-orquestrador.v2.md
f7c671407ee8228fc301d89917692cd74167d5a9c4a3b491e7c2860b0c4bf94b  contratos/PARA-O-DONO.md
12f48051d6cec27cbc93beac2e9e79239726f4a7c70d2d5a4c2c54162ad10bc8  contratos/REVISAO-CONTRATOS-1.md
046e10cbb7e7aaa23e2fd414eeae349a9dd34c1cb70efa90aef41d2977a899c9  contratos/REVISAO-CONTRATOS-2.md
