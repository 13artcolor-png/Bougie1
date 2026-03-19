# Bougie1 - Outil d'analyse de bougies en temps reel

## Description
Interface de visualisation et analyse de bougies de trading en temps reel.
- Ecran 1 (Radiographie) : decompose une bougie en micro-intervalles pour voir sa progression interne
- Ecran 2 (Analyse visuelle) : affiche les bougies avec outils de dessin et echelle graduee

## Stack technique
- Backend : Python + FastAPI + MetaTrader5
- Frontend : React + TypeScript + Vite + Tailwind CSS
- Communication : WebSocket temps reel (1 message/seconde)

## Architecture
```
backend/          # FastAPI + connexion MT5
  mt5/            # Connexion et recuperation de donnees MT5
  ws/             # WebSocket endpoint
  api/            # Routes REST
  utils/          # Utilitaires
frontend/         # React + Vite
  src/components/ # Composants React
  src/hooks/      # Hooks personnalises
  src/api/        # Client API
  src/types/      # Types TypeScript
```

## Commandes
- Backend : `cd backend && pip install -r requirements.txt && python main.py`
- Frontend dev : `cd frontend && npm install && npm run dev`
- Production : `start.bat` (build frontend + lance backend qui sert le build)

## Regles globales
1. **JAMAIS de donnees fictives** — toujours des donnees reelles
2. **Tester et verifier avant chaque livraison** — backend: curl, frontend: Pierre teste
3. **WebSearch au moindre doute** — ZERO tentative a l'aveugle
4. **Resolution a la racine** — jamais de pansement, toujours la cause profonde
5. **Ne jamais affirmer "c'est corrige"** sans preuve concrete
6. **Ne jamais supposer** — chercher le probleme a la racine
7. **Taille de police minimum : 18px** pour TOUS les elements UI
8. **Auto-sauvegarde** obligatoire sur tous les champs de configuration (onchange)
9. **Commentaires en francais**
10. **Le projet doit etre lisible** la taille des fenetres doivent etre adaptative, eviter les barres de defilement

## PRIORITE 1 - VERIFICATION ET TESTS (OBLIGATOIRE)

### REGLE ABSOLUE: Ne JAMAIS affirmer qu'une correction fonctionne sans preuve

**Cette section a priorite sur TOUTES les autres regles. A appliquer SYSTEMATIQUEMENT.**

1. **Backend (Python, API FastAPI)**:
   - Tu PEUX verifier via curl/commandes
   - **FAIS-LE AVANT de dire "c'est corrige"**
   - Exemple: `curl http://localhost:8111/api/health`

2. **Frontend (JavaScript, HTML, CSS)**:
   - Tu NE PEUX PAS tester dans le navigateur
   - **Dis TOUJOURS**: "J'ai modifie le code, mais je ne peux pas tester dans le navigateur. Veuillez rafraichir et me dire ce que vous voyez."
   - N'affirme JAMAIS "c'est corrige" ou "ca fonctionne" pour du code frontend

3. **Avant de considerer une tache terminee**:
   - Backend: Execute un test curl/python pour confirmer
   - Frontend: Demande a l'utilisateur de tester et attends sa confirmation
   - Si le test echoue, corrige et reteste immediatement

4. **INTERDICTIONS STRICTES**:
   - Ne dis pas "je verifie" si tu ne peux pas reellement verifier
   - Ne dis pas "c'est corrige" sans preuve concrete
   - Ne fais pas plusieurs tentatives en esperant que ca marche - analyse le probleme d'abord

## IMPORTANT - Philosophie du Projet

- **REGLE D'OR : RESOLUTION A LA RACINE (ZERO BAND-AID)**
    - Ne jamais proposer de "pansement" ou de solution temporaire.
    - Toujours identifier l'origine reelle du probleme et la corriger definitivement.
    - Si un probleme revient, c'est que la correction etait insuffisante : analyser et traiter la cause profonde.
    - Ne jamais demander de relancer le bot si l'origine du probleme n'a pas ete corrigee.
    - Cette regle est PRIORITAIRE et INALIENABLE.
