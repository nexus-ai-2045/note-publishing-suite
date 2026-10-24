declare module "markdown-it" {
  export default class MarkdownIt {
    constructor(options?: any);
    options: any;
    renderer: any;
    parse(source: string, env: any): any[];
  }
}
