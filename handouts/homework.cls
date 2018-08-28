\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{handout}[2009/11/30 v0.1 Jim Fowler's Homework class]

% Passes and class options to the underlying article class
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}
\ProcessOptions

% Load LaTeX's article class
\LoadClass[12pt]{article}

\makeatletter
\newcommand{\@course}{Mathematics}
\newcommand{\course}[1]{\renewcommand{\@course}{#1}}
\makeatother

\date{\ifcase\month\or Winter\or Winter\or March\or Spring\or Spring\or Spring\or Summer\or Summer\or Autumn\or Autumn\or Autumn\or Autumn\fi\space\number\year}

\usepackage{graphicx}
\usepackage{geometry}
\geometry{margin=1.25in,left=1.25in,top=0.5in,bottom=0.5in}

\usepackage[compact]{titlesec}
\makeatletter
\renewcommand{\maketitle}{%
  \begin{center}
    \textbf{Linear Algebra and Differential Equations: \@title} \\
    \@course \quad {\ifcase\month\or Winter\or Winter\or March\or Spring\or Spring\or Spring\or Summer\or Autumn\or Autumn\or Autumn\or Autumn\or Autumn\fi\space\number\year}
  \end{center}
  }
\makeatother

\titleformat{\section}{\bfseries}{}{0pt}{}

\usepackage{amsmath}
\usepackage{amsthm}
\newtheorem{theorem}{Theorem}
\newtheorem{corollary}[theorem]{Corollary}
\newtheorem{lemma}[theorem]{Lemma}
\newtheorem{proposition}[theorem]{Proposition}

\theoremstyle{definition}
\newtheorem{remark}[theorem]{Remark}
\newtheorem{example}[theorem]{Example}
\newtheorem{definition}[theorem]{Definition}

\usepackage{amssymb}
\newcommand{\R}{\mathbb{R}}
\newcommand{\N}{\mathbb{N}}

\usepackage{fmtcount}% http://ctan.org/pkg/fmtcount

\newcounter{problem}
\newenvironment{problem}{\makebox[0pt][r]{\refstepcounter{problem}\textbf{P\padzeroes[2]{\decimal{problem}}.}\hspace{1em}}\ignorespaces}{\vspace{1ex}}

\newenvironment{problem*}{\makebox[0pt][r]{\refstepcounter{problem}\textbf{$\ast$ P\padzeroes[2]{\decimal{problem}}.}\hspace{1em}}\ignorespaces}{\vspace{1ex}}
\setlength{\parindent}{0in}
\setlength{\parskip}{1ex}

\newenvironment{inspiration}{\vspace{-5ex}\begin{center}\footnotesize\em}{\end{center}\vspace{-2ex}}
\newcommand{\byline}[1]{ \rm---#1} 

\usepackage{nopageno}

%\geometry{margin=1cm}

% That's all, folks!
\endinput
