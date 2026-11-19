export interface AuthorProfile {
  readonly name: string;
  readonly initials: string;
  readonly handle: string;
  readonly githubUrl: string;
  readonly githubApiUrl: string;
  readonly repoName: string;
  readonly repoUrl: string;
  readonly issuesUrl: string;
  readonly avatarUrl: string;
  readonly institution: string;
  readonly institutionShort: string;
  readonly location: string;
  readonly countryCode: string;
  readonly tagline: string;
  readonly memberSince: number;
  readonly defaultPublicRepos: number;
  readonly defaultFollowers: number;
  readonly coreStack: readonly string[];
}

export const AUTHOR_PROFILE: AuthorProfile = {
  name: 'Rodrigo Pinheiro',
  initials: 'RP',
  handle: 'rodrigop07',
  githubUrl: 'https://github.com/rodrigop07',
  githubApiUrl: 'https://api.github.com/users/rodrigop07',
  repoName: 'rodrigop07/f1-overall',
  repoUrl: 'https://github.com/rodrigop07/f1-overall',
  issuesUrl: 'https://github.com/rodrigop07/f1-overall/issues',
  avatarUrl: 'https://avatars.githubusercontent.com/u/80424398?v=4',
  institution: 'Universidade Federal do Cariri (UFCA)',
  institutionShort: 'UFCA',
  location: 'Brasil',
  countryCode: 'BRA',
  tagline: 'Building in public, documenting the work, and making the next contribution easier.',
  memberSince: 2021,
  defaultPublicRepos: 21,
  defaultFollowers: 9,
  coreStack: ['Python', 'TypeScript', 'React', 'FastAPI', 'SQLite', 'Docker', 'C', 'C++', 'Assembly'],
};
