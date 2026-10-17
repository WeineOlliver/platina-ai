import {
  exchangeNpssoForCode,
  exchangeCodeForAccessToken,
  makeUniversalSearch,
  getUserTitles,
  getUserTrophiesEarnedForTitle,
  getTitleTrophies,
} from 'psn-api';

export interface PsnTrophySyncResult {
  psnId: string;
  game: string;
  platform: string;
  totalTrophies: number;
  unlockedCount: number;
  progressPercentage: number;
  trophies: Array<{
    name: string;
    type: string;
    detail: string;
    isUnlocked: boolean;
    earnedDateTime?: string;
    isMissable?: boolean;
    chapterOrLocation?: string;
  }>;
}

export class PsnCrawlerService {
  private authTokens: any = null;
  private npsso: string;

  constructor() {
    this.npsso = process.env.PSN_WORKER_NPSSO || '';
  }

  private async getAuth() {
    if (!this.npsso) {
      throw new Error('PSN_WORKER_NPSSO não configurado nas variáveis de ambiente.');
    }
    if (!this.authTokens) {
      const accessCode = await exchangeNpssoForCode(this.npsso);
      this.authTokens = await exchangeCodeForAccessToken(accessCode);
    }
    return this.authTokens;
  }

  async getPlayerTrophies(psnId: string, gameKeyword: string = 'Grand Theft Auto V'): Promise<PsnTrophySyncResult> {
    const auth = await this.getAuth();

    // 1. Search for user accountId by onlineId
    const searchRes = await makeUniversalSearch(auth, psnId, 'SocialAllAccounts');
    const domain = searchRes.domainResponses?.[0];
    const userResult = domain?.results?.[0];
    const accountId = userResult?.socialMetadata?.accountId;

    if (!accountId) {
      throw new Error(`Perfil da PSN não encontrado para o ID "${psnId}".`);
    }

    // 2. Fetch user played titles
    const titlesRes = await getUserTitles(auth, accountId, { limit: 100 });
    const targetTitle = titlesRes.trophyTitles.find((t: any) =>
      t.trophyTitleName.toLowerCase().includes(gameKeyword.toLowerCase())
    );

    if (!targetTitle) {
      throw new Error(`Nenhum histórico de "${gameKeyword}" encontrado para o jogador "${psnId}".`);
    }

    const npCommId = targetTitle.npCommunicationId;

    // 3. Fetch full trophy definitions and user earned statuses
    const [userTrophies, titleTrophies] = await Promise.all([
      getUserTrophiesEarnedForTitle(auth, accountId, npCommId, 'all'),
      getTitleTrophies(auth, npCommId, 'all'),
    ]);

    const titleMap = new Map<number, any>();
    for (const t of titleTrophies.trophies) {
      titleMap.set(t.trophyId, t);
    }

    const trophies = userTrophies.trophies.map((ut: any) => {
      const meta = titleMap.get(ut.trophyId) || {};
      const name = meta.trophyName || `Troféu #${ut.trophyId}`;
      const detail = meta.trophyDetail || '';
      
      // Known missable or challenging criteria detection
      const isMissable = 
        name.includes('Masterminds') || 
        name.includes('Elitist') || 
        name.includes('Cryptozoologist') ||
        detail.toLowerCase().includes('missable') ||
        detail.toLowerCase().includes('criminal mastermind');

      return {
        name,
        type: meta.trophyType || 'bronze',
        detail,
        isUnlocked: Boolean(ut.earned),
        earnedDateTime: ut.earnedDateTime,
        isMissable,
        chapterOrLocation: ut.trophyGroupId === 'default' ? 'Modo História / Base' : `DLC / Grupo ${ut.trophyGroupId}`,
      };
    });

    const unlockedCount = trophies.filter((t: any) => t.isUnlocked).length;

    return {
      psnId,
      game: targetTitle.trophyTitleName,
      platform: targetTitle.trophyTitlePlatform,
      totalTrophies: trophies.length,
      unlockedCount,
      progressPercentage: targetTitle.progress,
      trophies,
    };
  }
}

export const psnCrawlerService = new PsnCrawlerService();
