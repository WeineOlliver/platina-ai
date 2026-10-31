import {
  exchangeNpssoForCode,
  exchangeCodeForAccessToken,
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

import { env } from '../../config/env.js';

export class PsnCrawlerService {
  private authTokens: any = null;

  private getNpsso(): string {
    return env.PSN_WORKER_NPSSO || process.env.PSN_WORKER_NPSSO || '';
  }

  private async getAuth() {
    const npsso = this.getNpsso();
    if (!npsso) {
      throw new Error('PSN_WORKER_NPSSO environment variable is not configured.');
    }
    if (!this.authTokens) {
      const accessCode = await exchangeNpssoForCode(npsso);
      this.authTokens = await exchangeCodeForAccessToken(accessCode);
    }
    return this.authTokens;
  }

  async getPlayerTrophies(gameKeyword: string = 'Grand Theft Auto V'): Promise<PsnTrophySyncResult> {
    const auth = await this.getAuth();

    // 1. Fetch user played titles using authenticated owner account 'me'
    const titlesRes = await getUserTitles(auth, 'me', { limit: 100 });
    const targetTitle = titlesRes.trophyTitles.find((t: any) =>
      t.trophyTitleName.toLowerCase().includes(gameKeyword.toLowerCase())
    );

    if (!targetTitle) {
      throw new Error(`No trophy history for "${gameKeyword}" found on the project owner profile.`);
    }

    const npCommId = targetTitle.npCommunicationId;

    // 2. Fetch full trophy definitions and user earned statuses using 'me'
    const [userTrophies, titleTrophies] = await Promise.all([
      getUserTrophiesEarnedForTitle(auth, 'me', npCommId, 'all'),
      getTitleTrophies(auth, npCommId, 'all'),
    ]);

    const titleMap = new Map<number, any>();
    for (const t of titleTrophies.trophies) {
      titleMap.set(t.trophyId, t);
    }

    const trophies = userTrophies.trophies.map((ut: any) => {
      const meta = titleMap.get(ut.trophyId) || {};
      const name = meta.trophyName || `Trophy #${ut.trophyId}`;
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
        chapterOrLocation: ut.trophyGroupId === 'default' ? 'Story Mode / Base' : `DLC / Group ${ut.trophyGroupId}`,
      };
    });

    const unlockedCount = trophies.filter((t: any) => t.isUnlocked).length;

    return {
      psnId: 'me',
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
