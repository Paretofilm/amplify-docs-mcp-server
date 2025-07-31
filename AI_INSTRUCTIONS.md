# CRITICAL INSTRUCTIONS FOR AI ASSISTANTS

## WHEN CREATING A NEW AMPLIFY GEN 2 + NEXT.JS APPLICATION

### THE ONLY CORRECT COMMAND:

```bash
npx create-amplify@latest --template nextjs
```

### NEVER USE:
- ❌ `npm create amplify@latest` (without --template nextjs)
- ❌ `npx create-amplify@latest` (without --template nextjs)
- ❌ Manual installation of Next.js after creating Amplify
- ❌ Any other variation

### WHY THIS IS CRITICAL:
1. Only `--template nextjs` ensures compatible versions
2. Manual package installation leads to dependency conflicts
3. Without the template, you get an incomplete setup

### WHEN ASKED TO CREATE AN AMPLIFY APP:
Always respond with:
```bash
npx create-amplify@latest --template nextjs
```

This is the ONLY way to ensure a working Amplify Gen 2 + Next.js setup.

## FOR EXISTING NEXT.JS PROJECTS:
If the project already exists, warn the user that manual integration often fails due to version conflicts. Recommend starting fresh with the template command above.